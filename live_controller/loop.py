"""
The live control loop: pulls real cluster state every tick, hands it to the
*same* MBFDMigrationScheduler validated in the offline simulator, and
applies whatever it decides -- binding new pods, migrating (delete+recreate)
pods that need to move, and powering worker nodes up/down via Docker.

Run with the venv active, against a running `kind` cluster:

    .venv/Scripts/python.exe -m live_controller.loop
"""

import sys
import time

from kubernetes import client as k8s

from live_controller import adapter, carbon_api, k8s_client, power, state_server
from live_controller.config import NAMESPACE, NODE_READY_TIMEOUT_SECONDS, POLL_INTERVAL_SECONDS
from src.metrics import carbon_emissions_kg, temperature_variation_c
from src.power_model import active_host_count, host_utilizations, total_energy_wh
from src.schedulers.mbfd_migration import MBFDMigrationScheduler

MAX_EVENTS = 100


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def wait_for_node_ready(api: k8s.CoreV1Api, node_name: str, timeout: int = NODE_READY_TIMEOUT_SECONDS) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        node = api.read_node(node_name)
        if k8s_client.is_ready(node):
            return True
        time.sleep(3)
    return False


class LiveController:
    def __init__(self) -> None:
        self.api = k8s_client.load()
        k8s_client.ensure_namespace(self.api)
        self.scheduler = MBFDMigrationScheduler()
        self.first_seen: dict[str, int] = {}
        self.tick = 0
        self.events: list[dict] = []
        state_server.start_background()

    def _record_event(self, event_type: str, message: str) -> None:
        self.events.append({"ts": time.time(), "type": event_type, "message": message})
        del self.events[:-MAX_EVENTS]

    def _publish_state(
        self,
        all_nodes,
        ready_names: set[str],
        tasks,
        placement: dict[str, str],
        metrics: dict,
    ) -> None:
        host_tasks: dict[str, int] = {}
        for host_name in placement.values():
            host_tasks[host_name] = host_tasks.get(host_name, 0) + 1

        hosts_json = []
        for node in all_nodes:
            name = node.metadata.name
            cordoned = k8s_client.is_cordoned(node)
            hosts_json.append(
                {
                    "id": name,
                    "ready": name in ready_names,
                    "cordoned": cordoned,
                    "task_count": host_tasks.get(name, 0),
                    "status": "active" if host_tasks.get(name, 0) > 0 else ("off" if cordoned else "idle"),
                }
            )

        tasks_json = [
            {
                "id": t.id,
                "host": placement.get(t.id),
                "cpu_demand": t.cpu_demand,
                "mem_demand": t.mem_demand,
            }
            for t in tasks
        ]

        state_server.update_state(
            {
                "tick": self.tick,
                "timestamp": time.time(),
                "tasks": tasks_json,
                "hosts": hosts_json,
                "metrics": metrics,
                "events": list(self.events),
            }
        )

    def run_forever(self) -> None:
        log(f"live controller started, polling every {POLL_INTERVAL_SECONDS}s")
        while True:
            try:
                self.tick_once()
            except Exception as exc:  # keep the loop alive across transient API hiccups
                log(f"tick {self.tick} failed: {exc!r}")
            self.tick += 1
            time.sleep(POLL_INTERVAL_SECONDS)

    def tick_once(self) -> None:
        all_nodes = k8s_client.list_worker_nodes(self.api)
        hosts_all = adapter.nodes_to_hosts(all_nodes)
        ready_names = {
            n.metadata.name
            for n in all_nodes
            if k8s_client.is_ready(n) and not k8s_client.is_cordoned(n)
        }

        pods = k8s_client.list_managed_pods(self.api, NAMESPACE)
        bound_pods = [p for p in pods if p.spec.node_name]
        prev_placement = {p.metadata.name: p.spec.node_name for p in bound_pods}

        tasks = adapter.pods_to_tasks(pods, self.tick, self.first_seen)
        adapter.forget_completed(self.first_seen, {t.id for t in tasks})

        if not tasks:
            log(f"tick {self.tick}: no active tasks")
            self._power_off_empty_hosts(ready_names, set())
            self._publish_state(all_nodes, ready_names, [], {}, self._metrics_snapshot(hosts_all, [], {}))
            return

        new_placement = self.scheduler.schedule_round(self.tick, tasks, hosts_all, prev_placement)

        needed_hosts = set(new_placement.values())
        hosts_to_wake = needed_hosts - ready_names
        for host_name in hosts_to_wake:
            log(f"tick {self.tick}: powering on node {host_name}")
            self._record_event("power_on", f"powering on node {host_name}")
            if not power.is_container_running(host_name):
                power.start_node_container(host_name)
            if k8s_client.is_cordoned(next(n for n in all_nodes if n.metadata.name == host_name)):
                k8s_client.uncordon(self.api, host_name)
            if not wait_for_node_ready(self.api, host_name):
                log(f"tick {self.tick}: WARNING node {host_name} did not become Ready in time")
            else:
                ready_names.add(host_name)

        moved, bound = 0, 0
        for task_id, target_host in new_placement.items():
            current_host = prev_placement.get(task_id)
            if current_host is None:
                k8s_client.bind_pod_to_node(self.api, task_id, target_host, NAMESPACE)
                self._record_event("bind", f"bound {task_id} to {target_host}")
                bound += 1
            elif current_host != target_host:
                task = next(t for t in tasks if t.id == task_id)
                k8s_client.recreate_pod_on_node(
                    self.api, task_id, target_host, task.cpu_demand, task.mem_demand, NAMESPACE
                )
                self._record_event("migrate", f"migrated {task_id} from {current_host} to {target_host}")
                moved += 1

        self._power_off_empty_hosts(ready_names, needed_hosts)

        metrics = self._metrics_snapshot(hosts_all, tasks, new_placement, migrations=moved, bound=bound)
        self._publish_state(all_nodes, ready_names, tasks, new_placement, metrics)

        log(
            f"tick {self.tick}: tasks={len(tasks)} bound={bound} migrated={moved} "
            f"active_hosts={len(needed_hosts)} energy_w={metrics.get('energy_w', 0):.1f} "
            f"carbon_kg={metrics.get('carbon_kg', 0):.4f}"
        )

    def _metrics_snapshot(
        self,
        hosts_all,
        tasks,
        placement: dict[str, str],
        migrations: int = 0,
        bound: int = 0,
    ) -> dict:
        """Energy/temperature/carbon for this tick, using the exact same
        Eq. (1)-(5) implementations the offline simulator uses (src/metrics.py,
        src/power_model.py) -- just over the actual tick interval instead of
        the simulator's synthetic ROUND_HOURS, and with a live grid-carbon
        reading (live_controller/carbon_api.py) instead of the static
        placeholder constant."""
        if not tasks:
            return {"energy_w": 0.0, "temp_variation_c": 0.0, "carbon_kg": 0.0, "active_hosts": 0}

        round_hours = POLL_INTERVAL_SECONDS / 3600.0
        cpu_util, _mem_util = host_utilizations(hosts_all, tasks, placement)
        energy_wh = total_energy_wh(hosts_all, cpu_util, round_hours)
        carbon_intensity = carbon_api.get_carbon_intensity_kg_per_kwh()
        return {
            "energy_w": energy_wh / round_hours,
            "temp_variation_c": temperature_variation_c(hosts_all, cpu_util),
            "carbon_kg": carbon_emissions_kg(energy_wh, gamma=carbon_intensity),
            "carbon_intensity_kg_per_kwh": carbon_intensity,
            "active_hosts": active_host_count(cpu_util),
            "migrations": migrations,
            "bound": bound,
        }

    def _power_off_empty_hosts(self, ready_names: set[str], needed_hosts: set[str]) -> None:
        idle = ready_names - needed_hosts
        for host_name in idle:
            log(f"tick {self.tick}: node {host_name} is idle, cordoning and powering down")
            self._record_event("power_off", f"node {host_name} idle, powering down")
            k8s_client.cordon(self.api, host_name)
            power.stop_node_container(host_name)


def main() -> None:
    LiveController().run_forever()


if __name__ == "__main__":
    main()

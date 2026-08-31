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

from live_controller import adapter, k8s_client, power
from live_controller.config import NAMESPACE, NODE_READY_TIMEOUT_SECONDS, POLL_INTERVAL_SECONDS
from src.schedulers.mbfd_migration import MBFDMigrationScheduler


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
            return

        new_placement = self.scheduler.schedule_round(self.tick, tasks, hosts_all, prev_placement)

        needed_hosts = set(new_placement.values())
        hosts_to_wake = needed_hosts - ready_names
        for host_name in hosts_to_wake:
            log(f"tick {self.tick}: powering on node {host_name}")
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
                bound += 1
            elif current_host != target_host:
                task = next(t for t in tasks if t.id == task_id)
                k8s_client.recreate_pod_on_node(
                    self.api, task_id, target_host, task.cpu_demand, task.mem_demand, NAMESPACE
                )
                moved += 1

        self._power_off_empty_hosts(ready_names, needed_hosts)

        log(
            f"tick {self.tick}: tasks={len(tasks)} bound={bound} migrated={moved} "
            f"active_hosts={len(needed_hosts)}"
        )

    def _power_off_empty_hosts(self, ready_names: set[str], needed_hosts: set[str]) -> None:
        idle = ready_names - needed_hosts
        for host_name in idle:
            log(f"tick {self.tick}: node {host_name} is idle, cordoning and powering down")
            k8s_client.cordon(self.api, host_name)
            power.stop_node_container(host_name)


def main() -> None:
    LiveController().run_forever()


if __name__ == "__main__":
    main()

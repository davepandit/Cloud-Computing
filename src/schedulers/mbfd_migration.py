"""
MBFD + migration-cost-aware consolidation -- the project's core algorithmic
novelty (see NOVELTY.md, rows "Objective function" and "Load awareness").

Unlike plain MBFD (mbfd.py), this scheduler is *sticky*: a running task stays
on its current host unless an explicit evacuation is worth it. Every
CONSOLIDATION_INTERVAL_ROUNDS rounds it looks for lightly-loaded ("sparse")
hosts and checks whether relocating everything on them elsewhere would save
more energy -- over those tasks' *remaining* expected lifetime -- than the
one-time migration cost of moving them. New arrivals are still bin-packed
with best-fit onto already-active hosts, so consolidation quality stays
comparable to plain MBFD while the migration count stays low.
"""

from src import config
from src.binpack import CapacityError, HostLoad, best_fit_host, loads_from_placement
from src.hosts import Host
from src.metrics import migration_cost_wh
from src.power_model import host_power_w
from src.workload import Task


class MBFDMigrationScheduler:
    name = "mbfd-migration"

    def schedule_round(
        self,
        round_idx: int,
        active_tasks: list[Task],
        hosts: list[Host],
        prev_placement: dict[int, int],
    ) -> dict[int, int]:
        tasks_by_id = {t.id: t for t in active_tasks}
        hosts_by_id = {h.id: h for h in hosts}

        # Step 1: continuing tasks keep their host. Departures already freed
        # capacity, so every surviving placement is still feasible.
        placement = {tid: hid for tid, hid in prev_placement.items() if tid in tasks_by_id}
        loads = loads_from_placement(tasks_by_id, placement)

        # Step 2: place new arrivals, preferring to pack onto already-active hosts.
        new_arrivals = sorted(
            (t for t in active_tasks if t.id not in placement),
            key=lambda t: t.cpu_demand,
            reverse=True,
        )
        for task in new_arrivals:
            host_id = best_fit_host(task, hosts, loads)
            if host_id is None:
                raise CapacityError(f"no host can fit task {task.id}")
            load = loads.setdefault(host_id, HostLoad())
            load.used_cpu += task.cpu_demand
            load.used_mem += task.mem_demand
            placement[task.id] = host_id

        # Step 3: periodically look for evacuation opportunities.
        if round_idx % config.CONSOLIDATION_INTERVAL_ROUNDS == 0:
            placement, loads = self._try_consolidate(
                round_idx, tasks_by_id, hosts_by_id, hosts, placement, loads
            )

        return placement

    def _try_consolidate(self, round_idx, tasks_by_id, hosts_by_id, hosts, placement, loads):
        def util(host_id: int) -> float:
            h = hosts_by_id[host_id]
            load = loads.get(host_id, HostLoad())
            return load.used_cpu / h.cpu_capacity

        active_host_ids = [hid for hid, ld in loads.items() if ld.used_cpu > 0]
        sparse_ids = sorted(
            (hid for hid in active_host_ids if util(hid) < config.SPARSE_HOST_UTIL_THRESHOLD),
            key=util,
        )

        for evac_id in sparse_ids:
            tasks_on_host = [t for tid, t in tasks_by_id.items() if placement.get(tid) == evac_id]
            if not tasks_on_host:
                continue

            trial_loads = {hid: HostLoad(ld.used_cpu, ld.used_mem) for hid, ld in loads.items()}
            trial_updates: dict[int, int] = {}
            feasible = True
            for task in sorted(tasks_on_host, key=lambda t: t.cpu_demand, reverse=True):
                target = best_fit_host(task, hosts, trial_loads, exclude={evac_id})
                if target is None:
                    feasible = False
                    break
                load = trial_loads.setdefault(target, HostLoad())
                load.used_cpu += task.cpu_demand
                load.used_mem += task.mem_demand
                trial_updates[task.id] = target

            if not feasible:
                continue

            evac_host = hosts_by_id[evac_id]
            power_before = host_power_w(evac_host, loads[evac_id].used_cpu / evac_host.cpu_capacity)

            power_delta_targets = 0.0
            touched_hosts = set(trial_updates.values())
            for hid in touched_hosts:
                h = hosts_by_id[hid]
                before_util = loads.get(hid, HostLoad()).used_cpu / h.cpu_capacity
                after_util = trial_loads[hid].used_cpu / h.cpu_capacity
                power_delta_targets += host_power_w(h, after_util) - host_power_w(h, before_util)

            net_power_saved_w = power_before - power_delta_targets
            if net_power_saved_w <= 0:
                continue  # moving these tasks would not actually reduce power draw

            avg_remaining_rounds = sum(
                max(1, t.end_round - round_idx) for t in tasks_on_host
            ) / len(tasks_on_host)
            energy_saved_wh = net_power_saved_w * config.ROUND_HOURS * avg_remaining_rounds
            cost_wh = migration_cost_wh(len(tasks_on_host))

            if energy_saved_wh > cost_wh:
                for tid, hid in trial_updates.items():
                    placement[tid] = hid
                loads = trial_loads
                loads[evac_id] = HostLoad()

        return placement, loads

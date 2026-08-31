"""
Naive round-robin baseline -- the realistic "before" state most schedulers
still ship with (see NOVELTY.md, row "Baselines compared").

Once a task is placed it is never moved again (a real round-robin scheduler
does not migrate running work); each *new* arrival is handed to the next
host in a fixed rotation, regardless of how loaded that host already is.
This is what spreads load evenly across every node "for no reason."
"""

from src.binpack import HostLoad, fits, loads_from_placement
from src.hosts import Host
from src.workload import Task


class RoundRobinScheduler:
    name = "round-robin"

    def __init__(self, hosts: list[Host]):
        self._hosts = hosts
        self._next_index = 0

    def schedule_round(
        self,
        round_idx: int,
        active_tasks: list[Task],
        hosts: list[Host],
        prev_placement: dict[int, int],
    ) -> dict[int, int]:
        tasks_by_id = {t.id: t for t in active_tasks}
        placement = dict(prev_placement)
        loads = loads_from_placement(tasks_by_id, placement)

        new_arrivals = [t for t in active_tasks if t.id not in placement]
        n = len(hosts)
        for task in new_arrivals:
            for step in range(n):
                idx = (self._next_index + step) % n
                host = hosts[idx]
                load = loads.setdefault(host.id, HostLoad())
                if fits(host, load, task):
                    load.used_cpu += task.cpu_demand
                    load.used_mem += task.mem_demand
                    placement[task.id] = host.id
                    self._next_index = (idx + 1) % n
                    break
            else:
                raise RuntimeError("round-robin: no host in the pool can fit this task")
        return placement

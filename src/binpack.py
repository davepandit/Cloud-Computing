"""
Best-Fit-Decreasing bin-packing helpers, shared by the MBFD schedulers.

MBFD (Modified Best-Fit Decreasing) is the classic energy-aware VM
consolidation heuristic from Beloglazov & Buyya, "Energy Efficient Resource
Management in Virtualized Cloud Data Centers" (2010) -- it is not part of
the base ROA paper. We use it in place of ROA's population-based
metaheuristic specifically because it is cheap enough to re-run every
control-loop cycle (see NOVELTY.md, row "Core algorithm").

A task is "2D" here: it must fit both the host's remaining CPU and remaining
memory. Best-fit means: among hosts that can fit the task, choose the one
that will be left with the *least* spare capacity (tightest pack).
"""

from dataclasses import dataclass

from src.hosts import Host
from src.workload import Task


class CapacityError(Exception):
    """Raised when no host in the pool can fit a task."""


@dataclass
class HostLoad:
    used_cpu: float = 0.0
    used_mem: float = 0.0


def fits(host: Host, load: HostLoad, task: Task) -> bool:
    return (
        load.used_cpu + task.cpu_demand <= host.cpu_capacity
        and load.used_mem + task.mem_demand <= host.mem_capacity
    )


def remaining_fraction(host: Host, load: HostLoad, task: Task) -> float:
    """Combined spare-capacity fraction *after* placing task (lower = tighter fit)."""
    cpu_left = (host.cpu_capacity - load.used_cpu - task.cpu_demand) / host.cpu_capacity
    mem_left = (host.mem_capacity - load.used_mem - task.mem_demand) / host.mem_capacity
    return max(cpu_left, mem_left)


def best_fit_host(
    task: Task,
    hosts: list[Host],
    loads: dict[int, HostLoad],
    exclude: set[int] | None = None,
) -> int | None:
    """Pick the feasible host that ends up tightest-packed after placement."""
    exclude = exclude or set()
    best_id, best_score = None, None
    for host in hosts:
        if host.id in exclude:
            continue
        load = loads.setdefault(host.id, HostLoad())
        if not fits(host, load, task):
            continue
        score = remaining_fraction(host, load, task)
        if best_score is None or score < best_score:
            best_id, best_score = host.id, score
    return best_id


def best_fit_decreasing(tasks: list[Task], hosts: list[Host]) -> dict[int, int]:
    """Stateless full bin-packing: sorts tasks by CPU demand descending and
    places each on the tightest-fitting host, ignoring any prior placement.
    Used by the plain MBFD scheduler (src/schedulers/mbfd.py)."""
    sorted_tasks = sorted(tasks, key=lambda t: t.cpu_demand, reverse=True)
    loads: dict[int, HostLoad] = {}
    placement: dict[int, int] = {}
    for task in sorted_tasks:
        host_id = best_fit_host(task, hosts, loads)
        if host_id is None:
            raise CapacityError(f"no host can fit task {task.id}")
        load = loads[host_id]
        load.used_cpu += task.cpu_demand
        load.used_mem += task.mem_demand
        placement[task.id] = host_id
    return placement


def loads_from_placement(
    tasks_by_id: dict[int, Task], placement: dict[int, int]
) -> dict[int, HostLoad]:
    loads: dict[int, HostLoad] = {}
    for task_id, host_id in placement.items():
        task = tasks_by_id[task_id]
        load = loads.setdefault(host_id, HostLoad())
        load.used_cpu += task.cpu_demand
        load.used_mem += task.mem_demand
    return loads

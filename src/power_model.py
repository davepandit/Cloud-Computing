"""
Power and utilization model -- implements Eq. (1) and (2) from the base paper.

    P_i(t) = P_idle + (P_max - P_idle) * u_i(t)                     (Eq. 2)
    E_total = sum_i integral_0^T P_i(t) dt                          (Eq. 1)

We evaluate this once per control-loop round instead of continuously, so the
integral becomes P_i * round_hours summed over hosts and rounds.
"""

from src.hosts import Host
from src.workload import Task


def host_utilizations(
    hosts: list[Host],
    active_tasks: list[Task],
    placement: dict[int, int],
) -> tuple[dict[int, float], dict[int, float]]:
    """Returns (cpu_util, mem_util) fractions per host id, both in [0, 1].

    Raises ValueError if the placement overcommits any host -- schedulers are
    expected to never produce an infeasible placement; this is a safety net,
    not a normal control-flow path.
    """
    used_cpu = {h.id: 0.0 for h in hosts}
    used_mem = {h.id: 0.0 for h in hosts}
    hosts_by_id = {h.id: h for h in hosts}

    for task in active_tasks:
        host_id = placement.get(task.id)
        if host_id is None:
            raise ValueError(f"task {task.id} has no placement")
        used_cpu[host_id] += task.cpu_demand
        used_mem[host_id] += task.mem_demand

    cpu_util, mem_util = {}, {}
    for h in hosts:
        cpu_util[h.id] = used_cpu[h.id] / h.cpu_capacity
        mem_util[h.id] = used_mem[h.id] / h.mem_capacity
        if cpu_util[h.id] > 1.0 + 1e-6 or mem_util[h.id] > 1.0 + 1e-6:
            raise ValueError(
                f"host {h.id} overcommitted: cpu={cpu_util[h.id]:.3f} mem={mem_util[h.id]:.3f}"
            )
    return cpu_util, mem_util


def host_power_w(host: Host, cpu_util: float) -> float:
    """Eq. (2). A host with zero tasks draws 0W -- it is powered down, not idle."""
    if cpu_util <= 0.0:
        return 0.0
    return host.p_idle + (host.p_max - host.p_idle) * min(cpu_util, 1.0)


def total_energy_wh(hosts: list[Host], cpu_util: dict[int, float], round_hours: float) -> float:
    """Eq. (1), discretized to one round."""
    total_w = sum(host_power_w(h, cpu_util[h.id]) for h in hosts)
    return total_w * round_hours


def active_host_count(cpu_util: dict[int, float]) -> int:
    return sum(1 for u in cpu_util.values() if u > 1e-9)

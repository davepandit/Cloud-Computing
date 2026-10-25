"""
Shared fitness evaluation for the population-based metaheuristic baselines
(GA, PSO, ACO -- see ga.py/pso.py/aco.py). Each one searches over "which
subset of hosts is powered on", not a full per-task assignment: this keeps
the search space O(num_hosts) instead of O(num_tasks), which is what makes
re-running a whole population/iteration search every control-loop round
tractable at all.

Given a candidate host subset, task placement is just best-fit-decreasing
bin-packing restricted to that subset (src/binpack.py, unchanged), and
fitness is the resulting total energy (Eq. 1/2 via src/power_model.py).
Minimizing energy already rewards using fewer hosts, since host_power_w
charges a P_idle floor per *active* host -- the same consolidation pressure
MBFD chases greedily, just reached here by population search instead.
"""

from src import config
from src.binpack import CapacityError, best_fit_decreasing
from src.hosts import Host
from src.power_model import host_utilizations, total_energy_wh
from src.workload import Task

INFEASIBLE_PENALTY = 1e9


def evaluate_active_set(
    tasks: list[Task], hosts: list[Host], active_ids: set[int]
) -> tuple[float, dict[int, int] | None]:
    """Bin-packs `tasks` onto only the hosts in `active_ids`. Returns
    (energy_wh, placement), or (INFEASIBLE_PENALTY, None) if that subset
    can't fit every task -- callers should let this steer the search away,
    never let an infeasible candidate win."""
    allowed = [h for h in hosts if h.id in active_ids]
    try:
        placement = best_fit_decreasing(tasks, allowed)
    except CapacityError:
        return INFEASIBLE_PENALTY, None
    cpu_util, _mem_util = host_utilizations(hosts, tasks, placement)
    energy_wh = total_energy_wh(hosts, cpu_util, config.ROUND_HOURS)
    return energy_wh, placement


def seeded_active_set(tasks: list[Task], hosts: list[Host]) -> set[int]:
    """A feasible, already-reasonably-consolidated starting point: whichever
    hosts plain best-fit-decreasing over the FULL pool actually used."""
    placement = best_fit_decreasing(tasks, hosts)
    return set(placement.values())

"""
Ant Colony Optimization scheduler -- population-based metaheuristic
baseline (see ga.py and _metaheuristic_common.py for the shared "which
hosts are on" search space). Stateless across rounds, like the GA/PSO
baselines and plain MBFD.

Each ant independently decides, per host, whether to switch it on with
probability proportional to that host's pheromone level. Pheromone
evaporates every iteration and is reinforced on the hosts used by the
iteration's best-performing ants (elitist update), so the colony converges
toward host subsets that packed tasks into low total energy.
"""

import random

from src import config
from src.binpack import best_fit_decreasing
from src.hosts import Host
from src.schedulers._metaheuristic_common import evaluate_active_set, seeded_active_set
from src.workload import Task


class ACOScheduler:
    name = "aco"

    def schedule_round(
        self,
        round_idx: int,
        active_tasks: list[Task],
        hosts: list[Host],
        prev_placement: dict[int, int],
    ) -> dict[int, int]:
        if not active_tasks:
            return {}

        rng = random.Random(round_idx)
        host_ids = [h.id for h in hosts]
        seed = seeded_active_set(active_tasks, hosts)
        num_ants = config.METAHEURISTIC_POPULATION_SIZE

        pheromone = {
            hid: config.ACO_PHEROMONE_INIT * (2.0 if hid in seed else 1.0) for hid in host_ids
        }

        best_fit, best_placement = float("inf"), None

        for _ in range(config.METAHEURISTIC_ITERATIONS):
            colony = []
            for _ant in range(num_ants):
                active_ids = {
                    hid for hid in host_ids if rng.random() < pheromone[hid] / (pheromone[hid] + 1.0)
                }
                if not active_ids:
                    active_ids = set(seed)
                fit, placement = evaluate_active_set(active_tasks, hosts, active_ids)
                colony.append((fit, active_ids))
                if fit < best_fit:
                    best_fit, best_placement = fit, placement

            for hid in host_ids:
                pheromone[hid] *= 1.0 - config.ACO_EVAPORATION

            colony.sort(key=lambda c: c[0])
            elite = colony[: max(1, num_ants // 4)]
            for fit, active_ids in elite:
                for hid in active_ids:
                    pheromone[hid] += 1.0 / (1.0 + fit)

        if best_placement is None:
            best_placement = best_fit_decreasing(active_tasks, hosts)
        return best_placement

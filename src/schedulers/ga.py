"""
Genetic Algorithm scheduler -- a population-based metaheuristic baseline,
standing in for the literature GA/PSO/ACO comparisons the base paper and
its predecessors use (see NOVELTY.md "Baselines compared"), without a
CloudSim dependency: it runs on the exact same Host/Task/power model as
every other scheduler here (see _metaheuristic_common.py).

Like plain MBFD, it recomputes the full placement from scratch every round
and keeps no state between rounds -- so it shows the same migration
thrashing that motivates mbfd_migration.py's novelty.

Each chromosome is a subset of hosts ("which hosts are on"). Crossover
mixes two parents' host membership per-host; mutation flips a few hosts'
membership; fitness is the resulting total energy, so the search is
pulled toward fewer active hosts same as MBFD, just via selection instead
of greedy bin-packing choices.
"""

import random

from src import config
from src.binpack import best_fit_decreasing
from src.hosts import Host
from src.schedulers._metaheuristic_common import evaluate_active_set, seeded_active_set
from src.workload import Task


class GAScheduler:
    name = "ga"

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
        pop_size = config.METAHEURISTIC_POPULATION_SIZE

        def random_individual() -> set[int]:
            ind = set(seed)
            for hid in host_ids:
                if rng.random() < 0.05:
                    ind.symmetric_difference_update({hid})
            return ind

        population = [set(seed)] + [random_individual() for _ in range(pop_size - 1)]
        best_fit, best_placement = float("inf"), None

        for _ in range(config.METAHEURISTIC_ITERATIONS):
            scored = []
            for ind in population:
                fit, placement = evaluate_active_set(active_tasks, hosts, ind)
                scored.append((fit, ind))
                if fit < best_fit:
                    best_fit, best_placement = fit, placement
            scored.sort(key=lambda x: x[0])
            survivors = [ind for _, ind in scored[: max(2, pop_size // 2)]]

            children = list(survivors)
            while len(children) < pop_size:
                p1, p2 = rng.sample(survivors, 2) if len(survivors) >= 2 else (survivors[0], survivors[0])
                child = set()
                for hid in host_ids:
                    if (hid in p1) if rng.random() < 0.5 else (hid in p2):
                        child.add(hid)
                for hid in host_ids:
                    if rng.random() < 0.03:
                        child.symmetric_difference_update({hid})
                children.append(child)
            population = children

        if best_placement is None:
            best_placement = best_fit_decreasing(active_tasks, hosts)
        return best_placement

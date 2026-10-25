"""
Particle Swarm Optimization scheduler -- population-based metaheuristic
baseline (see ga.py and _metaheuristic_common.py for why the search space
is "which hosts are on" rather than a full per-task assignment, and why
that is what keeps this tractable to re-run every round). Stateless across
rounds, like the GA/ACO baselines and plain MBFD.

Each particle is a continuous position vector, one value per host, decoded
to "host is on" when that value crosses 0.5. Standard PSO velocity update
pulls each particle toward its own best position and the swarm's best.
"""

import random

from src import config
from src.binpack import best_fit_decreasing
from src.hosts import Host
from src.schedulers._metaheuristic_common import evaluate_active_set, seeded_active_set
from src.workload import Task


class PSOScheduler:
    name = "pso"

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
        n = len(host_ids)
        seed = seeded_active_set(active_tasks, hosts)
        pop_size = config.METAHEURISTIC_POPULATION_SIZE

        positions = [
            [(0.7 if hid in seed else 0.3) + rng.uniform(-0.2, 0.2) for hid in host_ids]
            for _ in range(pop_size)
        ]
        velocities = [[0.0] * n for _ in range(pop_size)]

        def decode(pos: list[float]) -> set[int]:
            return {host_ids[i] for i in range(n) if pos[i] > 0.5}

        personal_best_pos = [list(p) for p in positions]
        personal_best_fit = [float("inf")] * pop_size
        global_best_pos, global_best_fit, global_best_placement = None, float("inf"), None

        for _ in range(config.METAHEURISTIC_ITERATIONS):
            for i, pos in enumerate(positions):
                fit, placement = evaluate_active_set(active_tasks, hosts, decode(pos))
                if fit < personal_best_fit[i]:
                    personal_best_fit[i] = fit
                    personal_best_pos[i] = list(pos)
                if fit < global_best_fit:
                    global_best_fit, global_best_pos, global_best_placement = fit, list(pos), placement

            if global_best_pos is None:
                continue
            for i, pos in enumerate(positions):
                vel = velocities[i]
                for d in range(n):
                    r1, r2 = rng.random(), rng.random()
                    vel[d] = (
                        config.PSO_INERTIA * vel[d]
                        + config.PSO_COGNITIVE * r1 * (personal_best_pos[i][d] - pos[d])
                        + config.PSO_SOCIAL * r2 * (global_best_pos[d] - pos[d])
                    )
                    pos[d] = min(1.0, max(0.0, pos[d] + vel[d]))

        if global_best_placement is None:
            global_best_placement = best_fit_decreasing(active_tasks, hosts)
        return global_best_placement

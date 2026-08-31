"""
Synthetic workload generator.

Produces a stream of tasks arriving over a number of control-loop rounds,
each with a CPU/memory demand and a running duration -- standing in for the
CEA-Curie HPC job trace the base paper uses. Task sizes are drawn from the
same MIPS/RAM ranges the paper reports for its VMs (see src/config.py); the
arrival process and duration distribution are our own choice, made explicit
here so the real CEA-Curie trace can be substituted later without touching
any scheduler code -- a scheduler only ever sees a list[Task].
"""

from dataclasses import dataclass
import random

from src import config


@dataclass
class Task:
    id: int
    arrival_round: int
    duration_rounds: int
    cpu_demand: float   # MIPS
    mem_demand: float   # MB

    @property
    def end_round(self) -> int:
        return self.arrival_round + self.duration_rounds

    def is_active_at(self, round_idx: int) -> bool:
        return self.arrival_round <= round_idx < self.end_round


def generate_workload(
    num_tasks: int,
    num_rounds: int,
    seed: int | None = None,
) -> list[Task]:
    """Spread `num_tasks` arrivals roughly evenly across `num_rounds` rounds
    (a simple homogeneous arrival process), each with a heavy-tailed duration
    around config.TASK_MEAN_DURATION_ROUNDS so most jobs are short but a few
    run long -- enough to create real consolidation opportunities."""
    rng = random.Random(seed)
    tasks = []
    for i in range(num_tasks):
        arrival = rng.randint(0, max(0, num_rounds - 1))
        duration = max(
            config.TASK_MIN_DURATION_ROUNDS,
            int(rng.expovariate(1.0 / config.TASK_MEAN_DURATION_ROUNDS)),
        )
        cpu_demand = rng.uniform(*config.TASK_CPU_DEMAND_RANGE)
        mem_demand = rng.uniform(*config.TASK_MEM_DEMAND_RANGE)
        tasks.append(
            Task(
                id=i,
                arrival_round=arrival,
                duration_rounds=duration,
                cpu_demand=cpu_demand,
                mem_demand=mem_demand,
            )
        )
    tasks.sort(key=lambda t: t.arrival_round)
    return tasks


def active_tasks_at(tasks: list[Task], round_idx: int) -> list[Task]:
    return [t for t in tasks if t.is_active_at(round_idx)]

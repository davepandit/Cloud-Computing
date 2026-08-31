"""
Plain MBFD -- recomputes best-fit-decreasing bin-packing from scratch every
round, for every currently active task, completely ignoring where each task
was placed last round.

This consolidates as tightly as possible each round (good energy), but two
runs of best-fit-decreasing on nearly-identical task sets can land on
different bin assignments, so a task can be shuffled between hosts every
round even though nothing about it changed. That's deliberate here: it is
the "before" case that motivates the migration-cost-aware scheduler in
mbfd_migration.py (see NOVELTY.md, row "Objective function").
"""

from src.binpack import best_fit_decreasing
from src.hosts import Host
from src.workload import Task


class MBFDScheduler:
    name = "mbfd"

    def schedule_round(
        self,
        round_idx: int,
        active_tasks: list[Task],
        hosts: list[Host],
        prev_placement: dict[int, int],
    ) -> dict[int, int]:
        return best_fit_decreasing(active_tasks, hosts)

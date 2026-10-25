"""
Sanity checks for the core simulation. Run with:

    .venv/Scripts/python.exe -m pytest tests/ -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.hosts import generate_hosts
from src.power_model import host_utilizations
from src.schedulers.aco import ACOScheduler
from src.schedulers.ga import GAScheduler
from src.schedulers.mbfd import MBFDScheduler
from src.schedulers.mbfd_migration import MBFDMigrationScheduler
from src.schedulers.pso import PSOScheduler
from src.schedulers.round_robin import RoundRobinScheduler
from src.simulate import run_simulation, summarize
from src.workload import generate_workload

SEED = 123
NUM_TASKS = 400
NUM_ROUNDS = 40


def _make_workload():
    hosts = generate_hosts(seed=SEED)
    tasks = generate_workload(num_tasks=NUM_TASKS, num_rounds=NUM_ROUNDS, seed=SEED)
    return hosts, tasks


def test_no_scheduler_overcommits_a_host():
    hosts, tasks = _make_workload()
    schedulers = (
        RoundRobinScheduler(hosts),
        MBFDScheduler(),
        MBFDMigrationScheduler(),
        GAScheduler(),
        PSOScheduler(),
        ACOScheduler(),
    )
    for scheduler in schedulers:
        prev_placement: dict[int, int] = {}
        for round_idx in range(NUM_ROUNDS):
            active = [t for t in tasks if t.is_active_at(round_idx)]
            active_ids = {t.id for t in active}
            prev_placement = {tid: hid for tid, hid in prev_placement.items() if tid in active_ids}
            placement = scheduler.schedule_round(round_idx, active, hosts, dict(prev_placement))
            host_utilizations(hosts, active, placement)  # raises ValueError if overcommitted
            prev_placement = placement


def test_round_robin_never_migrates_a_running_task():
    hosts, tasks = _make_workload()
    records = run_simulation(RoundRobinScheduler(hosts), tasks, hosts, num_rounds=NUM_ROUNDS)
    assert sum(r.migrations for r in records) == 0


def test_migration_aware_scheduler_migrates_far_less_than_plain_mbfd():
    hosts, tasks = _make_workload()
    plain = summarize(run_simulation(MBFDScheduler(), tasks, hosts, num_rounds=NUM_ROUNDS))
    aware = summarize(
        run_simulation(MBFDMigrationScheduler(), tasks, hosts, num_rounds=NUM_ROUNDS)
    )
    assert aware["total_migrations"] < plain["total_migrations"] / 10


def test_migration_aware_scheduler_energy_within_10pct_of_plain_mbfd():
    hosts, tasks = _make_workload()
    plain = summarize(run_simulation(MBFDScheduler(), tasks, hosts, num_rounds=NUM_ROUNDS))
    aware = summarize(
        run_simulation(MBFDMigrationScheduler(), tasks, hosts, num_rounds=NUM_ROUNDS)
    )
    assert aware["avg_energy_w"] < plain["avg_energy_w"] * 1.10


def test_both_mbfd_variants_beat_round_robin_on_energy():
    hosts, tasks = _make_workload()
    rr = summarize(run_simulation(RoundRobinScheduler(hosts), tasks, hosts, num_rounds=NUM_ROUNDS))
    plain = summarize(run_simulation(MBFDScheduler(), tasks, hosts, num_rounds=NUM_ROUNDS))
    aware = summarize(
        run_simulation(MBFDMigrationScheduler(), tasks, hosts, num_rounds=NUM_ROUNDS)
    )
    assert plain["avg_energy_w"] < rr["avg_energy_w"]
    assert aware["avg_energy_w"] < rr["avg_energy_w"]


if __name__ == "__main__":
    test_no_scheduler_overcommits_a_host()
    test_round_robin_never_migrates_a_running_task()
    test_migration_aware_scheduler_migrates_far_less_than_plain_mbfd()
    test_migration_aware_scheduler_energy_within_10pct_of_plain_mbfd()
    test_both_mbfd_variants_beat_round_robin_on_energy()
    print("all smoke tests passed")

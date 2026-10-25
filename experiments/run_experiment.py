"""
Reproduces the base paper's Fig. 2-4 style sweep (task volumes 500-3000) for
our three schedulers -- round-robin, plain MBFD, and migration-cost-aware
MBFD -- and adds the migration-count comparison that is the point of this
project's novelty.

Run from the project root with the venv active:

    .venv/Scripts/python.exe experiments/run_experiment.py

Outputs:
    experiments/results/summary.csv
    experiments/results/energy_vs_tasks.png
    experiments/results/temperature_vs_tasks.png
    experiments/results/carbon_vs_tasks.png
    experiments/results/migrations_vs_tasks.png
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt

from src import config
from src.hosts import generate_hosts
from src.schedulers.aco import ACOScheduler
from src.schedulers.ga import GAScheduler
from src.schedulers.mbfd import MBFDScheduler
from src.schedulers.mbfd_migration import MBFDMigrationScheduler
from src.schedulers.pso import PSOScheduler
from src.schedulers.round_robin import RoundRobinScheduler
from src.simulate import run_simulation, summarize
from src.workload import generate_workload

TASK_VOLUMES = [500, 1000, 1500, 2000, 2500, 3000]
NUM_ROUNDS = 100
SEED = 7
RESULTS_DIR = Path(__file__).resolve().parent / "results"

SCHEDULER_FACTORIES = {
    "round-robin": lambda hosts: RoundRobinScheduler(hosts),
    "mbfd": lambda hosts: MBFDScheduler(),
    "mbfd-migration": lambda hosts: MBFDMigrationScheduler(),
}

# GA/PSO/ACO re-run a whole population/iteration search every round (see
# src/schedulers/_metaheuristic_common.py), so each round costs roughly
# METAHEURISTIC_POPULATION_SIZE * METAHEURISTIC_ITERATIONS times one plain
# MBFD round. NUM_ROUNDS must stay equal to the main sweep's -- workload.py
# spreads `num_tasks` arrivals across `num_rounds`, so a different round
# count at the same num_tasks changes arrival density and makes energy
# numbers at that x-axis point not comparable to the other three
# schedulers'. To keep run_experiment.py finishing in minutes instead of
# hours, trim the number of task-volume points instead.
METAHEURISTIC_TASK_VOLUMES = [500, 1000, 1500]
METAHEURISTIC_NUM_ROUNDS = NUM_ROUNDS

METAHEURISTIC_FACTORIES = {
    "ga": lambda hosts: GAScheduler(),
    "pso": lambda hosts: PSOScheduler(),
    "aco": lambda hosts: ACOScheduler(),
}

ALL_SCHEDULER_NAMES = list(SCHEDULER_FACTORIES) + list(METAHEURISTIC_FACTORIES)


def _run_sweep(task_volumes: list[int], num_rounds: int, factories: dict) -> list[dict]:
    rows = []
    for num_tasks in task_volumes:
        hosts = generate_hosts(seed=SEED)
        tasks = generate_workload(num_tasks=num_tasks, num_rounds=num_rounds, seed=SEED)
        for name, factory in factories.items():
            scheduler = factory(hosts)
            records = run_simulation(scheduler, tasks, hosts, num_rounds=num_rounds)
            summary = summarize(records)
            row = {"num_tasks": num_tasks, "scheduler": name, **summary}
            rows.append(row)
            print(
                f"tasks={num_tasks:>5} scheduler={name:<15} "
                f"energy_w={summary['avg_energy_w']:>8.1f} "
                f"temp_c={summary['avg_temp_variation_c']:>6.2f} "
                f"carbon_kg={summary['total_carbon_kg']:>7.3f} "
                f"migrations={summary['total_migrations']:>6}"
            )
    return rows


def run_all() -> list[dict]:
    rows = _run_sweep(TASK_VOLUMES, NUM_ROUNDS, SCHEDULER_FACTORIES)
    rows += _run_sweep(METAHEURISTIC_TASK_VOLUMES, METAHEURISTIC_NUM_ROUNDS, METAHEURISTIC_FACTORIES)
    return rows


def write_csv(rows: list[dict]) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "summary.csv"
    fieldnames = list(rows[0].keys())
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return out_path


def plot_metric(rows: list[dict], metric: str, ylabel: str, filename: str) -> Path:
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for name in ALL_SCHEDULER_NAMES:
        xs = [r["num_tasks"] for r in rows if r["scheduler"] == name]
        ys = [r[metric] for r in rows if r["scheduler"] == name]
        if not xs:
            continue
        ax.plot(xs, ys, marker="o", label=name)
    ax.set_xlabel("No. of tasks")
    ax.set_ylabel(ylabel)
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out_path = RESULTS_DIR / filename
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def main():
    rows = run_all()
    csv_path = write_csv(rows)
    print(f"\nwrote {csv_path}")

    plots = [
        plot_metric(rows, "avg_energy_w", "Energy consumption (W)", "energy_vs_tasks.png"),
        plot_metric(rows, "avg_temp_variation_c", "Temperature variation (°C)", "temperature_vs_tasks.png"),
        plot_metric(rows, "total_carbon_kg", "Carbon emissions (kg CO2e)", "carbon_vs_tasks.png"),
        plot_metric(rows, "total_migrations", "Total migrations", "migrations_vs_tasks.png"),
    ]
    for p in plots:
        print(f"wrote {p}")


if __name__ == "__main__":
    main()

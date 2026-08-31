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
from src.schedulers.mbfd import MBFDScheduler
from src.schedulers.mbfd_migration import MBFDMigrationScheduler
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


def run_all() -> list[dict]:
    rows = []
    for num_tasks in TASK_VOLUMES:
        hosts = generate_hosts(seed=SEED)
        tasks = generate_workload(num_tasks=num_tasks, num_rounds=NUM_ROUNDS, seed=SEED)
        for name, factory in SCHEDULER_FACTORIES.items():
            scheduler = factory(hosts)
            records = run_simulation(scheduler, tasks, hosts, num_rounds=NUM_ROUNDS)
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
    for name in SCHEDULER_FACTORIES:
        xs = [r["num_tasks"] for r in rows if r["scheduler"] == name]
        ys = [r[metric] for r in rows if r["scheduler"] == name]
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

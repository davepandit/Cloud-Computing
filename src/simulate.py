"""
Multi-round simulation harness: runs a scheduler across the whole lifetime
of a workload, one control-loop cycle ("round") at a time, and records the
metrics needed for the Fig. 2-4 style comparison plots plus our own
migration-count metric.
"""

from dataclasses import dataclass

from src import config
from src.hosts import Host
from src.metrics import carbon_emissions_kg, temperature_variation_c
from src.power_model import active_host_count, host_utilizations, total_energy_wh
from src.workload import Task, active_tasks_at


@dataclass
class RoundRecord:
    round: int
    num_active_tasks: int
    active_hosts: int
    energy_wh: float
    temp_variation_c: float
    carbon_kg: float
    migrations: int


def run_simulation(
    scheduler,
    tasks: list[Task],
    hosts: list[Host],
    num_rounds: int,
    round_hours: float = config.ROUND_HOURS,
) -> list[RoundRecord]:
    records: list[RoundRecord] = []
    prev_placement: dict[int, int] = {}

    for round_idx in range(num_rounds):
        active = active_tasks_at(tasks, round_idx)
        active_ids = {t.id for t in active}
        prev_placement = {tid: hid for tid, hid in prev_placement.items() if tid in active_ids}

        new_placement = scheduler.schedule_round(round_idx, active, hosts, dict(prev_placement))

        cpu_util, _mem_util = host_utilizations(hosts, active, new_placement)
        energy_wh = total_energy_wh(hosts, cpu_util, round_hours)
        temp_var = temperature_variation_c(hosts, cpu_util)
        carbon_kg = carbon_emissions_kg(energy_wh)
        migrations = sum(
            1
            for tid, hid in new_placement.items()
            if tid in prev_placement and prev_placement[tid] != hid
        )

        records.append(
            RoundRecord(
                round=round_idx,
                num_active_tasks=len(active),
                active_hosts=active_host_count(cpu_util),
                energy_wh=energy_wh,
                temp_variation_c=temp_var,
                carbon_kg=carbon_kg,
                migrations=migrations,
            )
        )
        prev_placement = new_placement

    return records


def summarize(records: list[RoundRecord]) -> dict:
    n = len(records)
    return {
        "avg_energy_w": sum(r.energy_wh for r in records) / n / config.ROUND_HOURS,
        "avg_temp_variation_c": sum(r.temp_variation_c for r in records) / n,
        "total_carbon_kg": sum(r.carbon_kg for r in records),
        "total_migrations": sum(r.migrations for r in records),
        "avg_active_hosts": sum(r.active_hosts for r in records) / n,
    }

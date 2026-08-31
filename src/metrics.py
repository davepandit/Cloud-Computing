"""
Temperature variation, carbon emissions, and the multi-objective fitness
function -- Eq. (3), (4), (5), (6)/(7) from the base paper, extended with a
4th, migration-cost term (our novelty: see NOVELTY.md).

The paper measures per-host temperature but does not publish how it derives
temperature from utilization. We use a simple, explicit linear model so the
formulas are computable and the assumption is easy to see and swap out:

    T_i = T_ambient + T_scale * u_i        (ours; not in the paper)
    delta_T = mean_i |T_i - mean(T)|       (Eq. 3/4, unchanged)
"""

from src import config
from src.hosts import Host


def host_temperatures_c(hosts: list[Host], cpu_util: dict[int, float]) -> dict[int, float]:
    return {
        h.id: config.TEMP_AMBIENT_C + config.TEMP_SCALE_C * cpu_util[h.id]
        for h in hosts
    }


def temperature_variation_c(hosts: list[Host], cpu_util: dict[int, float]) -> float:
    """Eq. (3)/(4): mean absolute deviation from the mean host temperature."""
    temps = host_temperatures_c(hosts, cpu_util)
    values = list(temps.values())
    mean_t = sum(values) / len(values)
    return sum(abs(t - mean_t) for t in values) / len(values)


def carbon_emissions_kg(energy_wh: float, gamma: float = config.CARBON_INTENSITY_KG_PER_KWH) -> float:
    """Eq. (5): C = gamma * E, with E converted from Wh to kWh."""
    return gamma * (energy_wh / 1000.0)


def migration_cost_wh(num_migrations: int, cost_per_task: float = config.MIGRATION_COST_WH) -> float:
    """Our 4th objective term: a one-time energy-equivalent overhead per
    migrated task (network transfer + brief disruption), expressed in the
    same Wh units as the energy term so it can be added directly."""
    return num_migrations * cost_per_task


def fitness(
    energy_wh: float,
    temp_var_c: float,
    carbon_kg: float,
    migration_wh: float,
    norm: dict[str, float],
) -> float:
    """Eq. (6)/(7) extended with a migration-cost term:

        F = w1*E_norm + w2*dT_norm + w3*C_norm + w4*Migration_norm

    `norm` holds normalization denominators for each term so the weighted
    sum is comparable across differently-scaled quantities, matching the
    paper's requirement that terms be "normalized to maintain uniformity in
    scale" before being weighted.
    """
    e_n = energy_wh / norm["energy"]
    t_n = temp_var_c / norm["temp"]
    c_n = carbon_kg / norm["carbon"]
    m_n = migration_wh / norm["migration"]
    return (
        config.WEIGHT_ENERGY * e_n
        + config.WEIGHT_TEMP * t_n
        + config.WEIGHT_CARBON * c_n
        + config.WEIGHT_MIGRATION * m_n
    )

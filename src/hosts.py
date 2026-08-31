"""Physical host (PM) model."""

from dataclasses import dataclass
import random

from src import config


@dataclass
class Host:
    id: int
    cpu_capacity: float   # MIPS
    mem_capacity: float   # MB
    p_idle: float = config.P_IDLE_W
    p_max: float = config.P_MAX_W


def generate_hosts(num_hosts: int = config.NUM_HOSTS, seed: int | None = None) -> list[Host]:
    rng = random.Random(seed)
    hosts = []
    for i in range(num_hosts):
        cpu = rng.uniform(*config.HOST_CPU_CAPACITY_RANGE)
        mem = rng.uniform(*config.HOST_MEM_CAPACITY_RANGE)
        hosts.append(Host(id=i, cpu_capacity=cpu, mem_capacity=mem))
    return hosts

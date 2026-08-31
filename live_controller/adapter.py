"""
Converts real Kubernetes Node/Pod objects into the exact same Host/Task
dataclasses the offline simulator uses (src/hosts.py, src/workload.py), so
MBFDMigrationScheduler runs completely unmodified against a live cluster.

Host/Task ids are typed `int` in src/, but Python dataclasses don't enforce
that at runtime -- we use node/pod *names* (strings) as ids here, which the
scheduler only ever uses as opaque, hashable dict keys and never does
arithmetic on.
"""

from kubernetes import client

from live_controller.config import (
    ASSUMED_REMAINING_TICKS,
    DEMO_NODE_CPU_CAP_MILLICORES,
    DEMO_NODE_MEM_CAP_MI,
)
from live_controller.k8s_units import parse_cpu_millicores, parse_mem_mi
from src.hosts import Host
from src.workload import Task


def node_to_host(node: client.V1Node) -> Host:
    """Capped at DEMO_NODE_CPU_CAP_MILLICORES/DEMO_NODE_MEM_CAP_MI so the
    scheduler sees each node as demo-sized rather than laptop-sized -- see
    the comment on those constants in live_controller/config.py."""
    allocatable = node.status.allocatable
    real_cpu = parse_cpu_millicores(allocatable["cpu"])
    real_mem = parse_mem_mi(allocatable["memory"])
    return Host(
        id=node.metadata.name,
        cpu_capacity=min(real_cpu, DEMO_NODE_CPU_CAP_MILLICORES),
        mem_capacity=min(real_mem, DEMO_NODE_MEM_CAP_MI),
    )


def nodes_to_hosts(nodes: list[client.V1Node]) -> list[Host]:
    return [node_to_host(n) for n in nodes]


def pod_resource_requests(pod: client.V1Pod) -> tuple[float, float]:
    requests = pod.spec.containers[0].resources.requests or {}
    cpu = parse_cpu_millicores(requests.get("cpu", "0m"))
    mem = parse_mem_mi(requests.get("memory", "0Mi"))
    return cpu, mem


def pods_to_tasks(
    pods: list[client.V1Pod],
    current_tick: int,
    first_seen: dict[str, int],
) -> list[Task]:
    """`first_seen` is mutated in place: the first tick each pod name was
    observed, so remaining-lifetime estimates are relative to that, not to
    an ever-growing global tick count (see live_controller/config.py)."""
    tasks = []
    for pod in pods:
        name = pod.metadata.name
        if name not in first_seen:
            first_seen[name] = current_tick
        cpu, mem = pod_resource_requests(pod)
        tasks.append(
            Task(
                id=name,
                arrival_round=first_seen[name],
                duration_rounds=ASSUMED_REMAINING_TICKS,
                cpu_demand=cpu,
                mem_demand=mem,
            )
        )
    return tasks


def forget_completed(first_seen: dict[str, int], still_present: set[str]) -> None:
    for name in list(first_seen):
        if name not in still_present:
            del first_seen[name]

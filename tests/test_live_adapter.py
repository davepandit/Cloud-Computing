"""
Tests for live_controller's Kubernetes <-> simulator adapter. These use
hand-built kubernetes-client model objects and never touch a real cluster,
so they run in CI / offline just like the rest of the suite.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kubernetes import client

from live_controller.adapter import forget_completed, node_to_host, pods_to_tasks
from live_controller.k8s_units import (
    format_cpu_millicores,
    format_mem_mi,
    parse_cpu_millicores,
    parse_mem_mi,
)


def _make_node(name="green-cloud-worker", cpu="4", memory="8137648Ki"):
    return client.V1Node(
        metadata=client.V1ObjectMeta(name=name),
        status=client.V1NodeStatus(allocatable={"cpu": cpu, "memory": memory}),
    )


def _make_pod(name="task-0", cpu="250m", memory="128Mi"):
    return client.V1Pod(
        metadata=client.V1ObjectMeta(name=name),
        spec=client.V1PodSpec(
            containers=[
                client.V1Container(
                    name="task",
                    image="busybox",
                    resources=client.V1ResourceRequirements(
                        requests={"cpu": cpu, "memory": memory}
                    ),
                )
            ],
        ),
    )


def test_cpu_quantity_roundtrip():
    assert parse_cpu_millicores("500m") == 500.0
    assert parse_cpu_millicores("2") == 2000.0
    assert format_cpu_millicores(750) == "750m"


def test_mem_quantity_roundtrip():
    assert parse_mem_mi("512Mi") == 512.0
    assert parse_mem_mi("1Gi") == 1024.0
    assert format_mem_mi(256) == "256Mi"


def test_node_to_host_converts_allocatable_capacity():
    host = node_to_host(_make_node())
    assert host.id == "green-cloud-worker"
    # Capped at the demo node CPU/mem caps (see live_controller/config.py),
    # not the node's real (uncapped) allocatable capacity of 4000m / ~7947Mi.
    assert host.cpu_capacity == 1200.0
    assert host.mem_capacity == 1500.0


def test_pods_to_tasks_tracks_first_seen_tick_not_current_tick():
    first_seen: dict[str, int] = {}
    pod = _make_pod()

    first_pass = pods_to_tasks([pod], current_tick=5, first_seen=first_seen)
    assert first_pass[0].arrival_round == 5
    assert first_pass[0].cpu_demand == 250.0
    assert first_pass[0].mem_demand == 128.0

    # observed again three ticks later: arrival_round must NOT change
    second_pass = pods_to_tasks([pod], current_tick=8, first_seen=first_seen)
    assert second_pass[0].arrival_round == 5


def test_forget_completed_drops_pods_no_longer_present():
    first_seen = {"task-0": 1, "task-1": 2}
    forget_completed(first_seen, still_present={"task-1"})
    assert first_seen == {"task-1": 2}

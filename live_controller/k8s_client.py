"""Thin wrapper around the official Kubernetes Python client -- every call
the live controller needs to make against the cluster, in one place."""

from kubernetes import client, config as kube_config

from live_controller.config import NAMESPACE, SCHEDULER_NAME


def load() -> client.CoreV1Api:
    """Loads ~/.kube/config (what `kind` writes on cluster creation)."""
    kube_config.load_kube_config()
    return client.CoreV1Api()


def ensure_namespace(api: client.CoreV1Api, namespace: str = NAMESPACE) -> None:
    existing = {ns.metadata.name for ns in api.list_namespace().items}
    if namespace not in existing:
        api.create_namespace(client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace)))


def list_worker_nodes(api: client.CoreV1Api) -> list[client.V1Node]:
    nodes = api.list_node().items
    return [n for n in nodes if "node-role.kubernetes.io/control-plane" not in (n.metadata.labels or {})]


def is_ready(node: client.V1Node) -> bool:
    for cond in node.status.conditions or []:
        if cond.type == "Ready":
            return cond.status == "True"
    return False


def is_cordoned(node: client.V1Node) -> bool:
    return bool(node.spec.unschedulable)


def cordon(api: client.CoreV1Api, node_name: str) -> None:
    api.patch_node(node_name, {"spec": {"unschedulable": True}})


def uncordon(api: client.CoreV1Api, node_name: str) -> None:
    api.patch_node(node_name, {"spec": {"unschedulable": False}})


def list_managed_pods(api: client.CoreV1Api, namespace: str = NAMESPACE) -> list[client.V1Pod]:
    """Only pods in our demo namespace, and only ones still relevant to a
    scheduling decision (not already finished)."""
    pods = api.list_namespaced_pod(namespace).items
    return [p for p in pods if p.status.phase in ("Pending", "Running")]


def create_pending_pod(
    api: client.CoreV1Api,
    name: str,
    cpu_millicores: float,
    mem_mi: float,
    namespace: str = NAMESPACE,
) -> None:
    """Creates a pod with no nodeName and a custom schedulerName, so the
    built-in kube-scheduler ignores it and it sits Pending until our
    controller binds it (see bind_pod_to_node)."""
    from live_controller.k8s_units import format_cpu_millicores, format_mem_mi

    pod = client.V1Pod(
        metadata=client.V1ObjectMeta(name=name, labels={"app": "green-cloud-task"}),
        spec=client.V1PodSpec(
            scheduler_name=SCHEDULER_NAME,
            restart_policy="Never",
            containers=[
                client.V1Container(
                    name="task",
                    image="busybox:1.36",
                    command=["sleep", "999999"],
                    resources=client.V1ResourceRequirements(
                        requests={
                            "cpu": format_cpu_millicores(cpu_millicores),
                            "memory": format_mem_mi(mem_mi),
                        },
                        limits={
                            "cpu": format_cpu_millicores(cpu_millicores),
                            "memory": format_mem_mi(mem_mi),
                        },
                    ),
                )
            ],
        ),
    )
    api.create_namespaced_pod(namespace, pod)


def bind_pod_to_node(api: client.CoreV1Api, pod_name: str, node_name: str, namespace: str = NAMESPACE) -> None:
    """The actual mechanism a real custom Kubernetes scheduler uses to place
    a Pending pod -- creating a Binding object -- rather than a workaround."""
    binding = client.V1Binding(
        metadata=client.V1ObjectMeta(name=pod_name),
        target=client.V1ObjectReference(kind="Node", name=node_name, api_version="v1"),
    )
    api.create_namespaced_binding(namespace, binding, _preload_content=False)


def delete_pod(api: client.CoreV1Api, pod_name: str, namespace: str = NAMESPACE) -> None:
    api.delete_namespaced_pod(pod_name, namespace, grace_period_seconds=0)


def recreate_pod_on_node(
    api: client.CoreV1Api,
    pod_name: str,
    node_name: str,
    cpu_millicores: float,
    mem_mi: float,
    namespace: str = NAMESPACE,
) -> None:
    """Kubernetes pods are immutable w.r.t. nodeName: "migrating" a running
    pod means delete + recreate pinned to the new node. This is a real,
    brief disruption -- exactly the cost the migration-cost-aware scheduler
    is weighing against the energy savings (see docs/ARCHITECTURE.md)."""
    delete_pod(api, pod_name, namespace)
    from live_controller.k8s_units import format_cpu_millicores, format_mem_mi

    pod = client.V1Pod(
        metadata=client.V1ObjectMeta(name=pod_name, labels={"app": "green-cloud-task"}),
        spec=client.V1PodSpec(
            scheduler_name=SCHEDULER_NAME,
            restart_policy="Never",
            node_name=node_name,
            containers=[
                client.V1Container(
                    name="task",
                    image="busybox:1.36",
                    command=["sleep", "999999"],
                    resources=client.V1ResourceRequirements(
                        requests={
                            "cpu": format_cpu_millicores(cpu_millicores),
                            "memory": format_mem_mi(mem_mi),
                        },
                        limits={
                            "cpu": format_cpu_millicores(cpu_millicores),
                            "memory": format_mem_mi(mem_mi),
                        },
                    ),
                )
            ],
        ),
    )
    api.create_namespaced_pod(namespace, pod)

"""
Real power control for kind nodes. A kind "node" is a Docker container on
this machine (container name == Kubernetes node name), so stopping it really
does stop it consuming CPU/RAM on the host -- this is not a simulated or
faked power-down (see docs/ARCHITECTURE.md).
"""

import subprocess


def stop_node_container(node_name: str) -> None:
    subprocess.run(["docker", "stop", node_name], check=True, capture_output=True)


def start_node_container(node_name: str) -> None:
    subprocess.run(["docker", "start", node_name], check=True, capture_output=True)


def is_container_running(node_name: str) -> bool:
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", node_name],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"

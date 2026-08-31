#!/usr/bin/env bash
# Creates the kind cluster used by the live proof-of-concept.
# Requires Docker Desktop running. Run from the project root:
#   bash infra/setup_cluster.sh
set -euo pipefail

KIND=".tools/kind.exe"
CONFIG="infra/kind-config.yaml"

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is not running. Start Docker Desktop, then re-run this script." >&2
  exit 1
fi

if "$KIND" get clusters | grep -q "^green-cloud$"; then
  echo "cluster 'green-cloud' already exists"
else
  "$KIND" create cluster --config "$CONFIG"
fi

kubectl wait --for=condition=Ready nodes --all --timeout=120s
kubectl get nodes -o wide

echo "cluster ready. In two separate terminals, from the project root, run:"
echo "  .venv/Scripts/python.exe -m live_controller.loop"
echo "  .venv/Scripts/python.exe -m live_controller.demo_workload --duration 300"

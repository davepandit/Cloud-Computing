# Creates the kind cluster used by the live proof-of-concept.
# Requires Docker Desktop running. Run from the project root in PowerShell:
#   .\infra\setup_cluster.ps1

$ErrorActionPreference = "Stop"

$Kind = ".tools\kind.exe"
$Config = "infra\kind-config.yaml"

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker daemon is not running. Start Docker Desktop, then re-run this script."
    exit 1
}

$existing = & $Kind get clusters
if ($existing -contains "green-cloud") {
    Write-Host "cluster 'green-cloud' already exists"
} else {
    & $Kind create cluster --config $Config
}

kubectl wait --for=condition=Ready nodes --all --timeout=120s
kubectl get nodes -o wide

Write-Host ""
Write-Host "cluster ready. In two separate PowerShell windows, from the project root, run:"
Write-Host "  .venv\Scripts\python.exe -m live_controller.loop"
Write-Host "  .venv\Scripts\python.exe -m live_controller.demo_workload --duration 300"

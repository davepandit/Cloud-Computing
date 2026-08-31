# Deletes the kind cluster (and any node containers it created).
# Run from the project root in PowerShell:
#   .\infra\teardown_cluster.ps1

$ErrorActionPreference = "Stop"
& ".tools\kind.exe" delete cluster --name green-cloud

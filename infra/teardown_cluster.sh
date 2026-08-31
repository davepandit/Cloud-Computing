#!/usr/bin/env bash
# Deletes the kind cluster (and any node containers it created).
set -euo pipefail
.tools/kind.exe delete cluster --name green-cloud

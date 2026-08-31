# Green Cloud Scheduler

Energy-aware workload consolidation for IaaS control planes. Course project
extending the base paper **Reddy et al., "ROA: Energy and Environment Aware
Task Scheduling in Cloud Computing," ICSCDS 2025**.

See the project plan artifact for the full novelty comparison and phased
scope: it lays out what differs from the base paper (continuous control loop,
migration-cost-aware objective, live Kubernetes validation, carbon-intensity
time-shifting) and what is scheduled for midterm vs. the final term.

## Status: Step 1 (Must-have, standalone) -- done

This step implements and validates the **core algorithmic novelty** with no
live infrastructure yet: a synthetic workload run through three schedulers
in an offline, multi-round simulation.

| Scheduler | What it does |
|---|---|
| `round-robin` | Naive baseline. Never migrates a running task; spreads new arrivals evenly across every host regardless of load. |
| `mbfd` | Recomputes best-fit-decreasing bin-packing from scratch every round, for every active task, ignoring prior placement. Consolidates tightly but thrashes. |
| `mbfd-migration` | **Our novelty.** Sticky placement + a migration-cost term: only evacuates a lightly-loaded host when the projected energy savings (over the evacuated tasks' remaining lifetime) exceed the one-time cost of moving them. |

### Result so far

Run the experiment yourself (see below), but the headline finding at 3000
concurrent tasks: `mbfd-migration` matches `mbfd`'s energy consumption
(within ~3%) while cutting total migrations from **14,947 to 19** — a
>99% reduction — and this gap widens linearly with load, since plain MBFD's
migration count scales with task volume while ours stays flat. This is the
concrete evidence for the novelty claimed in the project plan.

## Setup

```
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

## Run the tests

```
.venv/Scripts/python.exe -m pytest tests/ -v
```

## Run the experiment

```
.venv/Scripts/python.exe experiments/run_experiment.py
```

Produces `experiments/results/summary.csv` and four plots (energy,
temperature variation, carbon emissions, migrations — all vs. task volume,
mirroring the base paper's Fig. 2-4 layout plus our own migration-count plot).

## Project layout

```
src/
  config.py             constants: host power range, task size ranges, weights
  hosts.py              Host model + generator
  workload.py           Task model + synthetic workload generator
  binpack.py            shared best-fit-decreasing bin-packing helper
  power_model.py        Eq. (1)/(2) from the base paper: utilization -> power -> energy
  metrics.py            Eq. (3)-(7): temperature variation, carbon, fitness function
  simulate.py           multi-round simulation harness + summary stats
  schedulers/
    round_robin.py
    mbfd.py
    mbfd_migration.py   the migration-cost-aware scheduler (core novelty)
experiments/
  run_experiment.py     sweeps task volumes 500-3000, writes CSV + plots
  results/              generated output (gitignored)
tests/
  test_smoke.py         capacity-safety and novelty-claim regression checks
```

## Modeling assumptions worth knowing before you present this

- Host power range (175W-250W idle/peak) and task/VM MIPS+RAM ranges are
  taken directly from the base paper's Section IV setup.
- The host pool (100 hosts, 6000-12000 MIPS each) is sized with headroom so
  every scheduler can place every task across the full 500-3000 task sweep;
  it is larger than the paper's 50-host setup because our workload is a
  continuous stream with overlapping task lifetimes, not a one-shot batch.
- Temperature-from-utilization (`T = T_ambient + T_scale * utilization`) and
  the carbon intensity constant (0.475 kg CO2/kWh, a placeholder global grid
  average) are **our own instrumentation choices** — the base paper reports
  these metrics but does not publish the formula it uses to derive them from
  utilization. The carbon constant is exactly what gets replaced by a live
  grid-carbon API call in the final-term extension.
- MBFD (Modified Best-Fit Decreasing) itself is not from the base paper; it's
  the classic energy-aware VM consolidation heuristic from Beloglazov &
  Buyya (2010), used here because it's cheap enough to re-run every
  control-loop cycle, unlike ROA's population-based metaheuristic.

## Status: Step 2 (Must-have, live proof-of-concept) -- code done, not yet run end-to-end

Implements the minimal live PoC from the midterm scope: a `kind` Kubernetes
cluster where a real controller reads real pods, runs the **same, unmodified**
`MBFDMigrationScheduler` from Step 1 against real Node/Pod objects, binds new
pods, migrates (delete+recreate) pods that need to move, and powers worker
nodes up/down by actually starting/stopping their Docker containers. Full
design rationale (why a controller and not a `kube-scheduler` plugin, what
"migration" and "power-down" concretely mean here) is in `docs/ARCHITECTURE.md`.

This has been unit-tested (`tests/test_live_adapter.py` — the Kubernetes
object <-> simulator adapter logic, no cluster required) but **not yet run
against a real cluster**, because Docker Desktop wasn't running when this was
built. `kind` itself is already downloaded to `.tools/kind.exe` (gitignored;
re-download with the command in Setup below if missing).

### To actually run the live demo

1. Start Docker Desktop.
2. From the project root, in **PowerShell** (use the `.ps1` scripts, not the
   `.sh` ones, unless you deliberately launch Git Bash by its full path --
   see the gotcha below):
   ```
   .\infra\setup_cluster.ps1
   ```
   This creates a 1-control-plane + 4-worker `kind` cluster named `green-cloud`.
3. In one terminal, start the controller:
   ```
   .venv\Scripts\python.exe -m live_controller.loop
   ```
4. In a second terminal, start the demo workload generator:
   ```
   .venv\Scripts\python.exe -m live_controller.demo_workload --duration 300
   ```
5. Watch it happen live: `kubectl get pods -n green-cloud-demo -o wide --watch`
   and `docker ps` (to see worker node containers actually stop and start).
6. When done: `.\infra\teardown_cluster.ps1`

**Gotcha on Windows machines with WSL installed:** plain `bash` in PowerShell
can resolve to `C:\Windows\System32\bash.exe` (the WSL launcher) instead of
Git Bash, depending on PATH order. WSL has its own separate home directory,
so `kubectl` run inside it won't find the kubeconfig `kind` just wrote to
your Windows user folder, and fails with a `localhost:8080 connection
refused` error even though the cluster is actually up. Use the `.ps1`
scripts from PowerShell directly to sidestep this; the `.sh` versions still
work if you launch Git Bash explicitly (its own icon/shortcut, or the full
path `C:\Program Files\Git\bin\bash.exe`), just not via a bare `bash` command
in PowerShell.

### Project layout (additions)

```
live_controller/
  config.py          live-loop-specific constants (poll interval, namespace, scheduler name)
  k8s_units.py        Kubernetes resource-quantity parsing (millicores, Mi)
  k8s_client.py        every Kubernetes API call the controller makes, in one place
  adapter.py           converts real Node/Pod objects into Host/Task (reuses src/ as-is)
  power.py             docker stop/start on kind node containers
  loop.py              the control loop itself
  demo_workload.py     spawns/retires small pods to feed the loop
infra/
  kind-config.yaml      1 control-plane + 4 worker kind cluster
  setup_cluster.sh       creates the cluster, prints next steps
  teardown_cluster.sh    deletes it
docs/
  ARCHITECTURE.md        full system diagram + design rationale for both tracks
```

## What's next (not yet implemented)

CloudSim reproduction of the paper's GA/PSO/ACO baselines is a stretch goal
for midterm. The fully automated forecast module, carbon-intensity
time-shifting via a live grid-carbon API, and the Grafana dashboard are
deferred to the final term, per the project plan.

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
    ga.py, pso.py, aco.py            GA/PSO/ACO metaheuristic baselines
    _metaheuristic_common.py         shared fitness eval for the three above
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
  carbon_api.py        live grid carbon-intensity lookup (Step 3)
  state_server.py      stdlib HTTP endpoint the frontend polls (Step 3)
frontend/               Next.js dashboard + benchmarking pages (Step 3)
infra/
  kind-config.yaml      1 control-plane + 4 worker kind cluster
  setup_cluster.sh       creates the cluster, prints next steps
  teardown_cluster.sh    deletes it
docs/
  ARCHITECTURE.md        full system diagram + design rationale for both tracks
```

## Status: Step 3 (frontend, more baselines, live carbon) -- done

Three additions, independent of each other:

### GA / PSO / ACO baselines (no CloudSim)

`src/schedulers/ga.py`, `pso.py`, `aco.py` add three population-based
metaheuristic baselines alongside round-robin/MBFD/MBFD-migration, without
depending on CloudSim or any new library. Each one searches over *which
hosts are powered on* (not a full per-task assignment -- see
`src/schedulers/_metaheuristic_common.py`): a candidate host subset is
scored by bin-packing the current tasks onto it with the existing
best-fit-decreasing helper and measuring the resulting total energy via
the same Eq. (1)/(2) power model every other scheduler uses. This keeps
the search space at `O(num_hosts)` instead of `O(num_tasks)`, which is
what makes rerunning a whole population/generations search tractable
every single control-loop round. Like plain MBFD, they keep no state
between rounds, so they reproduce the same migration-thrashing behavior
that motivates `mbfd_migration.py`'s novelty.

Because each round now costs roughly `population_size * iterations` times
one plain-MBFD round, `experiments/run_experiment.py` runs these three
over the *same* 100 rounds as the original three (arrival density has to
match for a given task count to be comparable -- see the comment in that
file) but over fewer task-volume points (500-1500 instead of 500-3000),
so the whole script still finishes in a few minutes. See
`METAHEURISTIC_TASK_VOLUMES` at the top of that file to change the
tradeoff.

### Live grid carbon-intensity API

`live_controller/carbon_api.py` replaces the static
`config.CARBON_INTENSITY_KG_PER_KWH` placeholder with a live reading from
the UK National Grid ESO Carbon Intensity API (free, no key required).
Pure stdlib (`urllib`), cached for 15 minutes, falls back to the static
constant on any network failure. Used only by the live controller
(`live_controller/loop.py`) -- the offline simulator still uses the static
constant, since a batch sweep has no real "now." The region (GB) is still
a placeholder choice, same as the constant it replaces; swap the URL for a
different provider (e.g. Electricity Maps, WattTime) to target a
different grid.

### Next.js frontend (`frontend/`)

Two pages:

- **`/` -- live dashboard.** Polls the live controller every 3s and shows
  active tasks, server (host) power/utilization state, live energy/carbon
  numbers, and an event log of binds/migrations/power-on/power-off. Reads
  its data from a tiny new stdlib HTTP endpoint the controller now runs on
  `localhost:8787/state` (`live_controller/state_server.py`) via a
  server-side Next.js API route (`/api/state`) -- no CORS needed, and the
  Python side needed no new dependency.
- **`/benchmarking` -- algorithm comparison.** Reads
  `experiments/results/summary.csv` (via `/api/benchmark`) and renders
  energy / temperature-variation / carbon / migration-count charts across
  all six schedulers, as hand-rolled inline SVG line charts (no charting
  library dependency).

Run it:

```
cd frontend
npm install
npm run dev
```

Then open `http://localhost:3000`. For the live dashboard to show real
data, also have `live_controller.loop` running (Step 2); for the
benchmarking page, run `experiments/run_experiment.py` first to produce
`summary.csv`.

## What's next (not yet implemented)

The fully automated forecast module and the Grafana dashboard are
deferred to the final term, per the project plan.

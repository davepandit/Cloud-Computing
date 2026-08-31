"""Live-controller-specific constants. Kept separate from src/config.py
because the live cluster works in real Kubernetes resource units
(millicores, Mi/Ki) rather than the simulator's arbitrary MIPS/MB units."""

CLUSTER_NAME = "green-cloud"
NAMESPACE = "green-cloud-demo"
SCHEDULER_NAME = "green-cloud-scheduler"   # pods must set this to skip the default scheduler

POLL_INTERVAL_SECONDS = 10

# How many more control-loop ticks a task is assumed to still need once first
# observed. The simulator (src/workload.py) knows each task's true remaining
# lifetime; a live controller does not, so this is a documented approximation
# used only for the migration cost/benefit estimate (see live_controller/adapter.py).
ASSUMED_REMAINING_TICKS = 10

# NOTE: the consolidation interval, sparse-host threshold, and migration cost
# used by the scheduling decision itself are NOT duplicated here -- the live
# controller runs the exact same src.schedulers.mbfd_migration.MBFDMigrationScheduler
# used in the simulator, so those thresholds come from src/config.py. Keeping
# a second copy here would risk the live cluster silently testing different
# heuristics than the ones validated in experiments/run_experiment.py.

NODE_READY_TIMEOUT_SECONDS = 90

# A real kind node inherits a big chunk of the laptop's actual CPU/memory
# (several cores, several GB) -- far more than the tiny demo_workload.py
# tasks (100-400m CPU, 64-256Mi memory each) could ever fill. Left alone,
# the scheduler correctly (and correctly!) never needs a second node, which
# is accurate but not a demonstrative multi-node demo. These caps make the
# controller treat each node as if it only had this much room, purely so a
# modest demo workload is enough to force real consolidation across several
# nodes and show real power-up/power-down cycles. This does NOT change
# Kubernetes' own admission control -- the real node can still hold more
# than this if something else ever schedules onto it.
DEMO_NODE_CPU_CAP_MILLICORES = 1200
DEMO_NODE_MEM_CAP_MI = 1500

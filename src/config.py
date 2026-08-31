"""
Simulation constants.

Host power range (P_IDLE_W, P_MAX_W) and the VM/task MIPS and RAM ranges are
taken directly from the base paper's experimental setup (Reddy et al., "ROA:
Energy and Environment Aware Task Scheduling in Cloud Computing", ICSCDS 2025,
Section IV): 50 hosts, idle power 175W, peak power 250W, VM MIPS 500-2000,
VM RAM 512MB-2GB.

TEMP_AMBIENT_C / TEMP_SCALE_C and CARBON_INTENSITY_KG_PER_KWH are our own
instrumentation choices (the paper measures temperature and carbon but does
not publish the formula it uses to derive them from utilization) documented
here so they are easy to challenge or replace -- e.g. swapping
CARBON_INTENSITY_KG_PER_KWH for a live grid-carbon API reading is exactly the
"carbon-intensity-aware" extension planned for the final term.
"""

# ---- Datacenter / host pool ----
# Sized so peak concurrent demand at the largest tested workload (3000 tasks,
# see experiments/run_experiment.py) stays comfortably under total pool
# capacity for every scheduler, including round-robin's less efficient packing.
NUM_HOSTS = 100
HOST_CPU_CAPACITY_RANGE = (6000.0, 12000.0)   # MIPS, aggregate of ~2-4 VM slots per host
HOST_MEM_CAPACITY_RANGE = (4096.0, 16384.0)   # MB

P_IDLE_W = 175.0
P_MAX_W = 250.0

# ---- Task / workload ----
TASK_CPU_DEMAND_RANGE = (500.0, 2000.0)   # MIPS, matches paper's per-VM MIPS range
TASK_MEM_DEMAND_RANGE = (512.0, 2048.0)   # MB
TASK_MEAN_DURATION_ROUNDS = 8              # heavy-tailed around this mean
TASK_MIN_DURATION_ROUNDS = 1

# ---- Simulation clock ----
ROUND_HOURS = 0.1   # one control-loop cycle = 6 simulated minutes, for Wh integration

# ---- Derived-metric assumptions (ours, not the paper's) ----
TEMP_AMBIENT_C = 22.0
TEMP_SCALE_C = 20.0   # host at 100% utilization runs ~T_AMBIENT + T_SCALE degrees hotter
CARBON_INTENSITY_KG_PER_KWH = 0.475   # placeholder global grid average; replaced by a live
                                       # carbon-intensity API in the final-term extension

# ---- Objective function weights (Eq. 6/7 in the base paper, extended with w4) ----
WEIGHT_ENERGY = 0.4
WEIGHT_TEMP = 0.2
WEIGHT_CARBON = 0.2
WEIGHT_MIGRATION = 0.2
assert abs(WEIGHT_ENERGY + WEIGHT_TEMP + WEIGHT_CARBON + WEIGHT_MIGRATION - 1.0) < 1e-9

# ---- Migration-cost-aware scheduler tuning ----
MIGRATION_COST_WH = 5.0          # one-time energy-equivalent overhead per migrated task
CONSOLIDATION_INTERVAL_ROUNDS = 5   # how often the migration-aware scheduler looks for
                                     # evacuation opportunities, instead of every round
SPARSE_HOST_UTIL_THRESHOLD = 0.30   # a host below this utilization is a candidate to evacuate

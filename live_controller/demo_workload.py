"""
Feeds the live control loop with a stream of small "tasks" (busybox pods),
each with a random CPU/memory request and a random lifetime -- standing in
for real workload arrivals and completions so there's something for
loop.py to actually consolidate and power down.

Run in a second terminal, alongside `python -m live_controller.loop`:

    .venv/Scripts/python.exe -m live_controller.demo_workload --duration 300
"""

import argparse
import random
import time

from live_controller import k8s_client
from live_controller.config import NAMESPACE

CPU_RANGE_MILLICORES = (100, 400)
MEM_RANGE_MI = (64, 256)
LIFETIME_RANGE_SECONDS = (45, 150)
SPAWN_INTERVAL_SECONDS = 6


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=int, default=300, help="how long to run, in seconds")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    api = k8s_client.load()
    k8s_client.ensure_namespace(api, NAMESPACE)

    expiring: dict[str, float] = {}
    counter = 0
    start = time.time()
    next_spawn = start

    print(f"demo workload running for {args.duration}s, spawning every {SPAWN_INTERVAL_SECONDS}s")
    while time.time() - start < args.duration:
        now = time.time()

        if now >= next_spawn:
            name = f"task-{counter}"
            counter += 1
            cpu = rng.uniform(*CPU_RANGE_MILLICORES)
            mem = rng.uniform(*MEM_RANGE_MI)
            lifetime = rng.uniform(*LIFETIME_RANGE_SECONDS)
            k8s_client.create_pending_pod(api, name, cpu, mem, NAMESPACE)
            expiring[name] = now + lifetime
            print(f"spawned {name} cpu={cpu:.0f}m mem={mem:.0f}Mi lifetime={lifetime:.0f}s")
            next_spawn = now + SPAWN_INTERVAL_SECONDS

        for name, expiry in list(expiring.items()):
            if now >= expiry:
                try:
                    k8s_client.delete_pod(api, name, NAMESPACE)
                    print(f"completed {name}")
                except Exception as exc:
                    print(f"could not delete {name}: {exc!r}")
                del expiring[name]

        time.sleep(1)

    print("demo workload finished spawning; letting remaining tasks run out naturally")


if __name__ == "__main__":
    main()

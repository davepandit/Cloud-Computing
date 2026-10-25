"""
Live grid carbon-intensity lookup, replacing the static
config.CARBON_INTENSITY_KG_PER_KWH placeholder (see its comment in
src/config.py) with a real reading from the UK National Grid ESO Carbon
Intensity API -- free, no API key required: https://carbonintensity.org.uk/.
The region (GB) is still a placeholder choice, same as the constant it
replaces, but the number is now live instead of fixed.

Uses only the standard library (urllib) so this doesn't add a new pip
dependency. Cached for CACHE_TTL_SECONDS: the live controller polls every
10s (live_controller/config.py), but grid intensity doesn't move on that
cadence and the API shouldn't be hit that often anyway. Falls back to the
static config constant on any failure (network, parsing, timeout) so a
flaky connection never crashes the control loop.
"""

import json
import time
import urllib.request

from src import config

CARBON_API_URL = "https://api.carbonintensity.org.uk/intensity"
CACHE_TTL_SECONDS = 900  # 15 minutes
REQUEST_TIMEOUT_SECONDS = 5

_cache: dict[str, float] = {}


def get_carbon_intensity_kg_per_kwh() -> float:
    """Current grid carbon intensity in kg CO2/kWh -- live if reachable and
    not stale, otherwise the last good cached reading, otherwise the
    static config.CARBON_INTENSITY_KG_PER_KWH fallback."""
    now = time.time()
    cached = _cache.get("value")
    if cached is not None and now - _cache.get("fetched_at", 0) < CACHE_TTL_SECONDS:
        return cached

    try:
        with urllib.request.urlopen(CARBON_API_URL, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
            payload = json.loads(resp.read())
        intensity = payload["data"][0]["intensity"]
        g_per_kwh = intensity["actual"] if intensity["actual"] is not None else intensity["forecast"]
        kg_per_kwh = g_per_kwh / 1000.0
        _cache["value"] = kg_per_kwh
        _cache["fetched_at"] = now
        return kg_per_kwh
    except Exception:
        return _cache.get("value", config.CARBON_INTENSITY_KG_PER_KWH)

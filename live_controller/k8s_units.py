"""
Parse Kubernetes resource quantity strings into plain floats, so the rest of
the live controller never has to think about suffixes.

CPU is normalized to millicores ("500m" -> 500.0, "2" -> 2000.0).
Memory is normalized to Mi ("8137648Ki" -> 7947.0, "512Mi" -> 512.0).
"""

_MEM_BINARY_SUFFIXES = {"Ki": 1 / 1024, "Mi": 1.0, "Gi": 1024.0, "Ti": 1024.0 * 1024.0}
_MEM_DECIMAL_SUFFIXES = {
    "k": 1000.0 / (1024.0 * 1024.0),
    "M": 1_000_000.0 / (1024.0 * 1024.0),
    "G": 1_000_000_000.0 / (1024.0 * 1024.0),
}


def parse_cpu_millicores(quantity: str) -> float:
    quantity = quantity.strip()
    if quantity.endswith("m"):
        return float(quantity[:-1])
    return float(quantity) * 1000.0


def parse_mem_mi(quantity: str) -> float:
    quantity = quantity.strip()
    for suffix, factor in _MEM_BINARY_SUFFIXES.items():
        if quantity.endswith(suffix):
            return float(quantity[: -len(suffix)]) * factor
    for suffix, factor in _MEM_DECIMAL_SUFFIXES.items():
        if quantity.endswith(suffix):
            return float(quantity[: -len(suffix)]) * factor
    # plain bytes
    return float(quantity) / (1024.0 * 1024.0)


def format_cpu_millicores(millicores: float) -> str:
    return f"{int(round(millicores))}m"


def format_mem_mi(mi: float) -> str:
    return f"{int(round(mi))}Mi"

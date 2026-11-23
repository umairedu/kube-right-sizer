import math
from dataclasses import dataclass
from statistics import mean

from kubernetes.utils import parse_quantity

MIN_CPU = 0.01  # 10m
MIN_MEMORY = 16 * 2**20  # 16Mi
MIN_CHANGE = 0.10  # smaller differences are noise, not worth a rollout
THROTTLED = 0.05  # above this the CPU numbers are capped by the limit


@dataclass
class Row:
    namespace: str
    kind: str
    name: str
    container: str
    current: dict
    recommended: dict
    avg_cpu: float
    peak_memory: float
    throttled: float | None = None


def p95(values):
    values = sorted(values)
    return values[min(len(values) - 1, int(len(values) * 0.95))]


# round() first so float noise like 174.00000000000003 does not become 175m
def cpu(cores):
    return f"{math.ceil(round(cores * 1000, 6))}m"


def memory(size):
    return f"{math.ceil(round(size / 2**20, 6))}Mi"


def recommend(cpu_usage, memory_usage, buffer_percent, throttled=None, cpu_limit_now=None):
    # No data means a new or idle container, not a container that needs nothing.
    if not cpu_usage or not memory_usage:
        return None
    factor = 1 + buffer_percent / 100
    cpu_request = max(mean(cpu_usage) * factor, MIN_CPU)
    memory_request = max(mean(memory_usage) * factor, MIN_MEMORY)
    # Going over the CPU limit only throttles, going over the memory limit is an
    # OOM kill. So CPU gets p95 and memory gets the peak.
    cpu_limit = max(p95(cpu_usage) * factor, cpu_request * 1.5)
    if throttled and throttled > THROTTLED and cpu_limit_now:
        # A throttled container can't use more than its limit, so the real need
        # is unknown. Double the limit and let next week's run measure again.
        cpu_limit = max(cpu_limit, float(parse_quantity(cpu_limit_now)) * 2)
    memory_limit = max(max(memory_usage) * factor, memory_request * 1.5)
    return {
        "requests": {"cpu": cpu(cpu_request), "memory": memory(memory_request)},
        "limits": {"cpu": cpu(cpu_limit), "memory": memory(memory_limit)},
    }


def changed(current, recommended):
    for section in ("requests", "limits"):
        for resource in ("cpu", "memory"):
            now = current.get(section, {}).get(resource)
            if not now:
                return True
            now = float(parse_quantity(now))
            new = float(parse_quantity(recommended[section][resource]))
            if now == 0 or abs(new - now) / now > MIN_CHANGE:
                return True
    return False

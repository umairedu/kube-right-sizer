import math

import requests

# Prometheus refuses range queries with more than 11,000 points per series,
# so the step grows with the window: 15s for short windows, ~1m for a week.
MAX_POINTS = 10_000


def query_range(url, query, start, end):
    step = max(15, math.ceil((end - start).total_seconds() / MAX_POINTS))
    params = {"query": query, "start": start.timestamp(), "end": end.timestamp(), "step": step}
    resp = requests.get(f"{url}/api/v1/query_range", params=params, timeout=60)
    resp.raise_for_status()
    values = [float(v) for series in resp.json()["data"]["result"] for _, v in series["values"]]
    return [v for v in values if math.isfinite(v)]


def query(url, promql, at):
    resp = requests.get(f"{url}/api/v1/query", params={"query": promql, "time": at.timestamp()}, timeout=60)
    resp.raise_for_status()
    result = resp.json()["data"]["result"]
    return float(result[0]["value"][1]) if result else None


def usage(url, workload, container, start, end):
    # backticks are a raw string in PromQL, so the regex needs no extra escaping
    selector = f'namespace="{workload.namespace}", pod=~`{workload.pod_regex}`, container="{container}"'
    cpu = query_range(url, f"rate(container_cpu_usage_seconds_total{{{selector}}}[5m])", start, end)
    memory = query_range(url, f"container_memory_working_set_bytes{{{selector}}}", start, end)
    # share of CFS periods where the container hit its CPU limit; None without a limit
    window = f"{math.ceil((end - start).total_seconds())}s"
    throttled = query(url, f"sum(increase(container_cpu_cfs_throttled_periods_total{{{selector}}}[{window}])) / "
                           f"sum(increase(container_cpu_cfs_periods_total{{{selector}}}[{window}]))", end)
    if throttled is not None and not math.isfinite(throttled):
        throttled = None
    return cpu, memory, throttled

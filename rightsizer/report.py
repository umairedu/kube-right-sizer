import html
from collections import defaultdict

import yaml
from kubernetes.utils import parse_quantity
from tabulate import tabulate

from .recommend import MIN_CHANGE, cpu, memory

COLUMNS = ["Namespace", "Workload", "Container", "CPU request", "CPU limit",
           "Memory request", "Memory limit", "Avg CPU", "Peak memory", "Throttled"]
FIELDS = [("requests", "cpu"), ("limits", "cpu"), ("requests", "memory"), ("limits", "memory")]
ANSI = {"up": "\033[33m", "down": "\033[32m", "new": "\033[36m"}


def _direction(now, new):
    if not now:
        return "new"
    now, new = float(parse_quantity(now)), float(parse_quantity(new))
    if now and abs(new - now) / now <= MIN_CHANGE:
        return "same"
    return "up" if new > now else "down"


def _cells(row):
    for section, resource in FIELDS:
        now = row.current.get(section, {}).get(resource)
        new = row.recommended[section][resource]
        yield now or "-", new, _direction(now, new)


def _workload(row):
    return f"{row.kind.lower()}/{row.name}"


def _usage(row):
    throttled = "-" if row.throttled is None else f"{row.throttled:.0%}"
    return [cpu(row.avg_cpu), memory(row.peak_memory), throttled]


def table(rows, color=False):
    data = []
    for row in rows:
        cells = []
        for now, new, direction in _cells(row):
            text = f"{now} -> {new}"
            if color and direction in ANSI:
                text = f"{ANSI[direction]}{text}\033[0m"
            cells.append(text)
        data.append([row.namespace, _workload(row), row.container, *cells, *_usage(row)])
    return tabulate(data, headers=COLUMNS)


def html_report(rows, title):
    lines = []
    for row in rows:
        tds = [f"<td>{html.escape(v)}</td>" for v in (row.namespace, _workload(row), row.container)]
        tds += [f'<td class="{d}">{html.escape(now)} &rarr; {html.escape(new)}</td>' for now, new, d in _cells(row)]
        tds += [f"<td>{v}</td>" for v in _usage(row)]
        lines.append(f"<tr>{''.join(tds)}</tr>")
    header = "".join(f"<th>{c}</th>" for c in COLUMNS)
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 24px; color: #222; }}
table {{ border-collapse: collapse; }}
th, td {{ border: 1px solid #ddd; padding: 6px 10px; text-align: left; white-space: nowrap; }}
th {{ background: #f4f4f4; }}
.up {{ color: #b26a00; font-weight: 600; }}
.down {{ color: #1b7f3b; font-weight: 600; }}
.new {{ color: #0b6fa4; font-weight: 600; }}
</style></head><body>
<h2>{html.escape(title)}</h2>
<p>Orange needs more than it has today, green can be lowered, blue has nothing set yet.</p>
<table><tr>{header}</tr>
{chr(10).join(lines)}
</table></body></html>
"""


def patches(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row.namespace, row.kind, row.name)].append(row)
    docs = []
    for (namespace, kind, name), group in groups.items():
        containers = [{"name": r.container, "resources": r.recommended} for r in group]
        docs.append({
            "apiVersion": "apps/v1",
            "kind": kind,
            "metadata": {"name": name, "namespace": namespace},
            "spec": {"template": {"spec": {"containers": containers}}},
        })
    return yaml.safe_dump_all(docs, sort_keys=False)

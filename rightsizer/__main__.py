import datetime as dt
import sys
from pathlib import Path
from statistics import mean

import requests
from slack_sdk.errors import SlackApiError

from . import kube, prometheus, report, slack
from .config import Settings
from .recommend import Row, changed, recommend


def log(message):
    print(message, file=sys.stderr, flush=True)


def period(hours):
    value, unit = (hours / 24, "day") if hours >= 24 else (hours, "hour")
    return f"{value:g} {unit}" + ("" if value == 1 else "s")


def analyze(settings):
    end = dt.datetime.now(dt.UTC)
    start = end - dt.timedelta(hours=settings.hours)
    core, apps = kube.connect()
    rows = []
    for namespace in kube.namespaces(core, settings.target_namespaces, settings.excluded_namespaces):
        for w in kube.list_workloads(core, apps, namespace):
            for container, current in w.containers.items():
                cpu, memory, throttled = prometheus.usage(settings.prometheus_url, w, container, start, end)
                cpu_limit_now = current["limits"].get("cpu")
                recommended = recommend(cpu, memory, settings.buffer_percent, throttled, cpu_limit_now)
                if recommended is None:
                    log(f"skip {namespace}/{w.kind.lower()}/{w.name} {container}: no metrics in the window")
                    continue
                rows.append(Row(namespace, w.kind, w.name, container, current, recommended,
                                mean(cpu), max(memory), throttled))
    return rows


def main():
    settings = Settings.from_env()
    log(f"analyzing the last {period(settings.hours)} from {settings.prometheus_url}")
    rows = [r for r in analyze(settings) if changed(r.current, r.recommended)]
    log(f"{len(rows)} containers need new requests or limits")
    if not rows:
        return

    title = f"Resource recommendations, last {period(settings.hours)}"
    html_report = report.html_report(rows, title)
    patches = report.patches(rows)
    if settings.output_format in ("table", "both"):
        print(report.table(rows, color=sys.stdout.isatty()))
    if settings.output_format in ("yaml", "both"):
        print("\n" + patches)

    if settings.output_dir:
        out = Path(settings.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "resource-report.html").write_text(html_report)
        (out / "recommendations.yaml").write_text(patches)
        log(f"wrote {out}/resource-report.html and {out}/recommendations.yaml")

    if settings.slack_token and settings.slack_channel:
        summary = (
            f"{title}: {len(rows)} containers need new requests or limits. "
            f"Requests are the mean usage, limits the p95 (CPU) and peak (memory), "
            f"plus a {settings.buffer_percent}% buffer. Report and patches are in the thread."
        )
        slack.send(settings.slack_token, settings.slack_channel, summary, html_report, patches,
                   settings.slack_verify_ssl)
        log(f"sent to Slack channel {settings.slack_channel}")


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as e:
        log(f"Prometheus query failed: {e}")
        sys.exit(1)
    except SlackApiError as e:
        log(f"Slack refused the message: {e.response['error']}")
        sys.exit(1)

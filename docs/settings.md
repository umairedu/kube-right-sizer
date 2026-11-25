# Settings

Everything is an environment variable. In the Helm chart they go under `env`, except the Slack ones, which have their own `slack` block so the token can live in a secret.

| Variable | Default | |
|---|---|---|
| `PROMETHEUS_URL` | `http://localhost:9090` | Needs the cAdvisor metrics: `container_cpu_usage_seconds_total`, `container_memory_working_set_bytes` and the `container_cpu_cfs_*` counters. |
| `TARGET_NAMESPACE` | empty | Comma-separated. Empty scans every namespace. |
| `EXCLUDED_NAMESPACES` | `kube-system,kube-public,kube-node-lease` | Skipped even if they're in `TARGET_NAMESPACE`. |
| `HOURS` | `168` | History to read. `0.5` works too. Prometheus has to keep at least this much. |
| `BUFFER_PERCENT` | `20` | Added on top of the measured usage. |
| `OUTPUT_FORMAT` | `both` | `table`, `yaml` or `both`, printed to the job log. |
| `OUTPUT_DIR` | empty | Also write `resource-report.html` and `recommendations.yaml` here. |
| `SLACK_TOKEN` | empty | Bot token. No token, no Slack. |
| `SLACK_CHANNEL` | empty | Channel ID or name. |
| `SLACK_VERIFY_SSL` | `true` | `false` only behind a proxy that re-signs TLS. |

Inside the cluster it uses its service account. Outside, it uses your current kubeconfig context.

A few floors the README table leaves out: a CPU request is never below `10m`, a memory request never below `16Mi`, and both limits are at least 1.5x their request. Bare pods and pods from Jobs are skipped, because they have no stable name to look up in Prometheus.

## The smallest values file

```yaml
env:
  PROMETHEUS_URL: http://prometheus-server.monitoring.svc:9090
```

Results only end up in the job log then: `kubectl -n right-sizer logs job/<name>`.

## Two namespaces, two weeks, Slack

Here the token is in a secret you create yourself, it runs on weekday mornings, and the buffer is smaller:

```bash
kubectl -n right-sizer create secret generic slack-bot --from-literal=SLACK_TOKEN=xoxb-...
```

```yaml
schedule: "0 7 * * 1-5"
env:
  PROMETHEUS_URL: http://kube-prometheus-stack-prometheus.monitoring.svc:9090
  TARGET_NAMESPACE: payments,checkout
  EXCLUDED_NAMESPACES: ""
  HOURS: "336"
  BUFFER_PERCENT: "10"
  OUTPUT_FORMAT: table
slack:
  channel: C0123456789
  existingSecret: slack-bot
```

## From your laptop

Port-forward your Prometheus (the service name will be different in your cluster) and run it from the clone. It uses whatever kube context is current, so check that first.

```bash
kubectl -n monitoring port-forward svc/prometheus 9090 &
uv sync
TARGET_NAMESPACE=shop OUTPUT_DIR=out uv run python -m rightsizer
```

`out/resource-report.html` is the same page that goes to Slack.

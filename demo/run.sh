#!/usr/bin/env bash
# Builds the image, starts a kind cluster with Prometheus and three badly sized
# apps, installs the chart and runs the CronJob once.
set -euo pipefail
cd "$(dirname "$0")/.."

CLUSTER=right-sizer-demo
CTX=kind-$CLUSTER
IMAGE=docker.io/umairedu/kube-right-sizer:demo
WAIT=${WAIT:-240}
k() { kubectl --context "$CTX" "$@"; }

if ! kind get clusters | grep -qx "$CLUSTER"; then
  previous=$(kubectl config current-context 2>/dev/null || true)
  kind create cluster --name "$CLUSTER"
  # kind switches your current context, put it back
  if [ -n "$previous" ]; then kubectl config use-context "$previous" >/dev/null; fi
fi

docker build -q -t "$IMAGE" .
kind load docker-image "$IMAGE" --name "$CLUSTER"

k apply -f demo/prometheus.yaml -f demo/apps.yaml
k -n monitoring rollout status deploy/prometheus --timeout=180s
k -n shop rollout status deploy/orders --timeout=180s
k -n shop rollout status deploy/search --timeout=180s
k -n billing rollout status deploy/invoices --timeout=180s

echo "waiting ${WAIT}s so Prometheus has some usage history"
sleep "$WAIT"

helm --kube-context "$CTX" upgrade --install right-sizer chart \
  -n right-sizer --create-namespace -f demo/values.yaml --wait
job=run-$(date +%s)
k -n right-sizer create job "$job" --from=cronjob/right-sizer
k -n right-sizer wait --for=condition=complete "job/$job" --timeout=180s
k -n right-sizer logs "job/$job"

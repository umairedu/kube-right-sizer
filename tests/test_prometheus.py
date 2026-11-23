from datetime import datetime, timedelta

from rightsizer import prometheus
from rightsizer.kube import Workload


class Response:
    def __init__(self, url):
        self.url = url

    def raise_for_status(self):
        pass

    def json(self):
        if self.url.endswith("/query"):
            return {"data": {"result": [{"value": [0, "0.42"]}]}}
        series = {"values": [[0, "0.1"], [60, "NaN"], [120, "0.3"]]}
        return {"data": {"result": [series, series]}}


def test_queries(monkeypatch):
    calls = []

    def get(url, params, timeout):
        calls.append(params)
        return Response(url)

    monkeypatch.setattr(prometheus.requests, "get", get)
    end = datetime(2026, 1, 31)
    w = Workload("shop", "Deployment", "orders", {})
    cpu, memory, throttled = prometheus.usage("http://prom", w, "app", end - timedelta(days=30), end)

    assert cpu == [0.1, 0.3, 0.1, 0.3]  # all pods, NaN dropped
    assert throttled == 0.42
    assert 'pod=~`orders-[a-z0-9]+-[a-z0-9]{5}`' in calls[0]["query"]
    assert 'container="app"' in calls[1]["query"]
    assert "[2592000s]" in calls[2]["query"]
    # 30 days at 60s would be 43,200 points, over the Prometheus limit
    assert calls[0]["step"] == 260

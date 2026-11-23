import yaml

from rightsizer import report
from rightsizer.recommend import Row, changed, recommend

MI = 2**20


def test_requests_follow_mean_and_limits_follow_p95_and_peak():
    cpu = [0.1] * 95 + [1.0] * 5
    memory = [100 * MI] * 99 + [300 * MI]
    rec = recommend(cpu, memory, buffer_percent=20)
    assert rec["requests"] == {"cpu": "174m", "memory": "123Mi"}
    # p95 lands on the spike for CPU, memory limit uses the single peak
    assert rec["limits"] == {"cpu": "1200m", "memory": "360Mi"}


def test_floor_for_idle_containers():
    rec = recommend([0.0001] * 10, [1 * MI] * 10, buffer_percent=20)
    assert rec["requests"] == {"cpu": "10m", "memory": "16Mi"}
    assert rec["limits"] == {"cpu": "15m", "memory": "24Mi"}


def test_throttled_container_gets_a_higher_cpu_limit():
    flat = [0.3] * 100  # pinned at its 300m limit
    rec = recommend(flat, [100 * MI] * 100, 20, throttled=0.9, cpu_limit_now="300m")
    assert rec["limits"]["cpu"] == "600m"
    # a little throttling is normal and changes nothing
    assert recommend(flat, [100 * MI] * 100, 20, throttled=0.01, cpu_limit_now="300m")["limits"]["cpu"] == "540m"


def test_no_metrics_means_no_recommendation():
    assert recommend([], [100 * MI], 20) is None
    assert recommend([0.1], [], 20) is None


def test_changed_understands_every_unit():
    rec = {"requests": {"cpu": "1000m", "memory": "128Mi"}, "limits": {"cpu": "2000m", "memory": "1Gi"}}
    same = {"requests": {"cpu": "1", "memory": "131072Ki"}, "limits": {"cpu": "2", "memory": "1024Mi"}}
    assert not changed(same, rec)
    assert changed({"requests": {"cpu": "1", "memory": "128Mi"}, "limits": {}}, rec)
    assert changed({**same, "limits": {"cpu": "2", "memory": "2Gi"}}, rec)


def test_small_differences_are_ignored():
    rec = {"requests": {"cpu": "105m", "memory": "100Mi"}, "limits": {"cpu": "200m", "memory": "200Mi"}}
    current = {"requests": {"cpu": "100m", "memory": "100Mi"}, "limits": {"cpu": "200m", "memory": "200Mi"}}
    assert not changed(current, rec)


def _row(namespace, name, container="app"):
    rec = {"requests": {"cpu": "50m", "memory": "64Mi"}, "limits": {"cpu": "100m", "memory": "128Mi"}}
    current = {"requests": {"cpu": "500m", "memory": "512Mi"}, "limits": {}}
    return Row(namespace, "Deployment", name, container, current, rec, 0.04, 60 * MI)


def test_same_container_name_in_two_namespaces_stays_separate():
    rows = [_row("shop", "orders"), _row("billing", "invoices"), _row("shop", "orders", "proxy")]
    docs = list(yaml.safe_load_all(report.patches(rows)))
    assert [(d["metadata"]["namespace"], d["metadata"]["name"]) for d in docs] == [
        ("shop", "orders"), ("billing", "invoices")]
    assert [c["name"] for c in docs[0]["spec"]["template"]["spec"]["containers"]] == ["app", "proxy"]


def test_table_shows_current_and_recommended():
    out = report.table([_row("shop", "orders")])
    assert "500m -> 50m" in out
    assert out.splitlines()[-1].endswith("-")  # no throttling data
    assert "- -> 100m" in out
    assert "deployment/orders" in out


def test_html_escapes_names():
    out = report.html_report([_row("shop", "<b>x</b>")], "title")
    assert "<b>x</b>" not in out
    assert "&lt;b&gt;" in out

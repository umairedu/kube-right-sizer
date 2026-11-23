import re
from datetime import datetime, timedelta
from types import SimpleNamespace as NS

from rightsizer.kube import Workload, list_workloads

T0 = datetime(2026, 1, 1)


def ref(kind, name):
    return NS(kind=kind, name=name, controller=True)


def pod(name, owner, cpu="100m", age=0):
    container = NS(name="app", resources=NS(requests={"cpu": cpu, "memory": "64Mi"}, limits=None))
    meta = NS(name=name, owner_references=[owner] if owner else None, creation_timestamp=T0 + timedelta(minutes=age))
    return NS(metadata=meta, spec=NS(containers=[container]))


class Core:
    def __init__(self, pods):
        self.pods = pods

    def list_namespaced_pod(self, namespace, field_selector):
        return NS(items=self.pods)


class Apps:
    def list_namespaced_replica_set(self, namespace):
        rs = NS(metadata=NS(name="orders-7bd4c9bbdf", owner_references=[ref("Deployment", "orders")]))
        return NS(items=[rs])


def test_pods_are_grouped_by_their_workload():
    pods = [
        pod("orders-7bd4c9bbdf-fz8fb", ref("ReplicaSet", "orders-7bd4c9bbdf"), cpu="100m", age=0),
        pod("orders-7bd4c9bbdf-k2x9q", ref("ReplicaSet", "orders-7bd4c9bbdf"), cpu="200m", age=5),
        pod("db-0", ref("StatefulSet", "db")),
        pod("debug", None),
        pod("backup-29000000-abcde", ref("Job", "backup-29000000")),
    ]
    workloads = list_workloads(Core(pods), Apps(), "shop")
    assert [(w.kind, w.name) for w in workloads] == [("Deployment", "orders"), ("StatefulSet", "db")]
    # the newest pod's spec is the one we compare against
    assert workloads[0].containers["app"] == {"requests": {"cpu": "200m", "memory": "64Mi"}, "limits": {}}


def test_pod_regex_does_not_match_similar_names():
    orders = re.compile(Workload("shop", "Deployment", "orders", {}).pod_regex)
    assert orders.fullmatch("orders-7bd4c9bbdf-fz8fb")
    assert not orders.fullmatch("orders-api-7bd4c9bbdf-fz8fb")
    db = re.compile(Workload("shop", "StatefulSet", "db", {}).pod_regex)
    assert db.fullmatch("db-12")
    assert not db.fullmatch("db-backup-0")

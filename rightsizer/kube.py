import re
from dataclasses import dataclass

from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException

# How each controller names its pods. One regex then matches every pod the
# workload had during the window, not only the pod that is running right now.
POD_SUFFIX = {
    "Deployment": r"-[a-z0-9]+-[a-z0-9]{5}",
    "StatefulSet": r"-[0-9]+",
    "DaemonSet": r"-[a-z0-9]{5}",
}


@dataclass
class Workload:
    namespace: str
    kind: str
    name: str
    containers: dict  # container name -> {"requests": {...}, "limits": {...}}

    @property
    def pod_regex(self):
        return re.escape(self.name) + POD_SUFFIX[self.kind]


def connect():
    try:
        config.load_incluster_config()
    except ConfigException:
        config.load_kube_config()
    return client.CoreV1Api(), client.AppsV1Api()


def namespaces(core, target, excluded):
    names = target or [ns.metadata.name for ns in core.list_namespace().items]
    return [n for n in names if n not in excluded]


def owner_of(pod, deployment_of_rs):
    refs = pod.metadata.owner_references or []
    if not refs:
        return None, pod.metadata.name
    ref = next((r for r in refs if r.controller), refs[0])
    if ref.kind == "ReplicaSet" and ref.name in deployment_of_rs:
        return "Deployment", deployment_of_rs[ref.name]
    return ref.kind, ref.name


def list_workloads(core, apps, namespace):
    deployment_of_rs = {}
    for rs in apps.list_namespaced_replica_set(namespace).items:
        for ref in rs.metadata.owner_references or []:
            if ref.kind == "Deployment":
                deployment_of_rs[rs.metadata.name] = ref.name

    workloads = {}
    pods = core.list_namespaced_pod(namespace, field_selector="status.phase=Running").items
    for pod in sorted(pods, key=lambda p: p.metadata.creation_timestamp):
        kind, name = owner_of(pod, deployment_of_rs)
        if kind not in POD_SUFFIX:
            continue  # bare pods, Jobs and custom controllers are left out
        # newest pod wins, so during a rollout we compare against the new spec
        containers = {c.name: _resources(c) for c in pod.spec.containers}
        workloads[(kind, name)] = Workload(namespace, kind, name, containers)
    return list(workloads.values())


def _resources(container):
    r = container.resources
    if not r:
        return {"requests": {}, "limits": {}}
    return {"requests": dict(r.requests or {}), "limits": dict(r.limits or {})}

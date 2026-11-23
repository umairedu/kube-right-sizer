import os
from dataclasses import dataclass


def _list(value):
    return [x.strip() for x in value.split(",") if x.strip()]


@dataclass
class Settings:
    prometheus_url: str
    target_namespaces: list
    excluded_namespaces: list
    hours: float
    buffer_percent: int
    output_format: str
    output_dir: str
    slack_token: str
    slack_channel: str
    slack_verify_ssl: bool

    @classmethod
    def from_env(cls, env=os.environ):
        settings = cls(
            prometheus_url=env.get("PROMETHEUS_URL", "http://localhost:9090").rstrip("/"),
            target_namespaces=_list(env.get("TARGET_NAMESPACE", "")),
            excluded_namespaces=_list(env.get("EXCLUDED_NAMESPACES", "kube-system,kube-public,kube-node-lease")),
            hours=float(env.get("HOURS", "168")),
            buffer_percent=int(env.get("BUFFER_PERCENT", "20")),
            output_format=env.get("OUTPUT_FORMAT", "both"),
            output_dir=env.get("OUTPUT_DIR", ""),
            slack_token=env.get("SLACK_TOKEN", ""),
            slack_channel=env.get("SLACK_CHANNEL", ""),
            slack_verify_ssl=env.get("SLACK_VERIFY_SSL", "true").lower() != "false",
        )
        if settings.output_format not in ("table", "yaml", "both"):
            raise ValueError(f"OUTPUT_FORMAT must be table, yaml or both, got {settings.output_format!r}")
        if settings.hours <= 0:
            raise ValueError("HOURS must be greater than 0")
        return settings

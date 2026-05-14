"""Thin wrapper around the Kubernetes Python client for observation tasks.

Auth strategy:
  - In-cluster : auto-detected via KUBERNETES_SERVICE_HOST env var.
  - Local/dev  : falls back to ~/.kube/config.
"""

from __future__ import annotations

import os
from typing import Any

from kubernetes import client, config
from kubernetes.client.rest import ApiException


def _load_kube_config() -> None:
    """Load kube config — in-cluster first, then local kubeconfig."""
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        config.load_incluster_config()
    else:
        config.load_kube_config()


class K8sClient:
    """Reads Kubernetes state: pods, events, logs, and resource metrics."""

    def __init__(self) -> None:
        _load_kube_config()
        self._core = client.CoreV1Api()
        self._metrics = client.CustomObjectsApi()

    # ── Pods ──────────────────────────────────────────────────────────────────

    def list_pods(self, namespace: str = "litmus") -> list[dict[str, Any]]:
        """Return a list of pod summaries in the given namespace."""
        resp = self._core.list_namespaced_pod(namespace=namespace)
        pods = []
        for pod in resp.items:
            containers = [c.name for c in (pod.spec.containers or [])]
            conditions = []
            if pod.status.conditions:
                for cond in pod.status.conditions:
                    if cond.status != "True":
                        conditions.append(f"{cond.type}: {cond.reason or cond.message or 'unknown'}")
            pods.append({
                "name": pod.metadata.name,
                "namespace": pod.metadata.namespace,
                "phase": pod.status.phase or "Unknown",
                "containers": containers,
                "conditions": conditions,
                "node": pod.spec.node_name,
                "start_time": str(pod.status.start_time) if pod.status.start_time else None,
            })
        return pods

    # ── Events ────────────────────────────────────────────────────────────────

    def get_pod_events(
        self, namespace: str = "litmus", pod_name: str | None = None
    ) -> list[dict[str, Any]]:
        """Return Kubernetes events, optionally filtered to a specific pod."""
        field_selector = ""
        if pod_name:
            field_selector = f"involvedObject.name={pod_name},involvedObject.kind=Pod"

        resp = self._core.list_namespaced_event(
            namespace=namespace,
            field_selector=field_selector or None,
        )

        events = []
        for ev in sorted(resp.items, key=lambda e: e.last_timestamp or e.event_time or "", reverse=True):
            events.append({
                "name": ev.metadata.name,
                "pod": ev.involved_object.name,
                "reason": ev.reason,
                "message": ev.message,
                "type": ev.type,                # Normal | Warning
                "count": ev.count,
                "first_time": str(ev.first_timestamp) if ev.first_timestamp else None,
                "last_time": str(ev.last_timestamp) if ev.last_timestamp else None,
            })
        return events

    # ── Logs ──────────────────────────────────────────────────────────────────

    def get_pod_logs(
        self,
        namespace: str = "litmus",
        pod_name: str = "",
        container: str | None = None,
        tail_lines: int = 100,
    ) -> str:
        """Return the last ``tail_lines`` lines of a pod/container's stdout log."""
        try:
            return self._core.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                container=container or None,
                tail_lines=tail_lines,
                timestamps=True,
            )
        except ApiException as exc:
            raise RuntimeError(f"Could not fetch logs for pod '{pod_name}': {exc.reason}")

    # ── Resource Usage (metrics-server) ───────────────────────────────────────

    def get_pod_resource_usage(self, namespace: str = "litmus") -> list[dict[str, Any]]:
        """Return CPU/memory usage per pod via the metrics-server API.

        Requires ``metrics.k8s.io`` to be deployed in the cluster.
        Raises ``RuntimeError`` with a helpful message if unavailable.
        """
        try:
            data = self._metrics.list_namespaced_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                namespace=namespace,
                plural="pods",
            )
        except ApiException as exc:
            if exc.status == 404:
                raise RuntimeError(
                    "metrics-server is not installed in this cluster. "
                    "Deploy metrics-server to enable CPU/memory usage queries."
                )
            raise RuntimeError(f"Metrics API error: {exc.reason}")

        usage = []
        for pod_metrics in data.get("items", []):
            containers = []
            for c in pod_metrics.get("containers", []):
                containers.append({
                    "name": c["name"],
                    "cpu": c["usage"].get("cpu", "n/a"),
                    "memory": c["usage"].get("memory", "n/a"),
                })
            usage.append({
                "pod": pod_metrics["metadata"]["name"],
                "namespace": pod_metrics["metadata"]["namespace"],
                "containers": containers,
                "timestamp": pod_metrics.get("timestamp"),
                "window": pod_metrics.get("window"),
            })
        return usage

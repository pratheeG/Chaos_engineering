"""LangChain tools for Kubernetes observation.

These tools wrap K8sClient and are designed to be plugged directly
into the Observer Agent once the API layer is validated.
"""

from __future__ import annotations

import json
from langchain_core.tools import tool

from services.k8s_client import K8sClient

# Single shared client instance
_k8s = K8sClient()


# ── Tools ─────────────────────────────────────────────────────────────────────

@tool
def list_pods(namespace: str = "litmus") -> str:
    """List all pods and their status in a Kubernetes namespace.

    Args:
        namespace: The Kubernetes namespace to query (default: 'litmus').
    """
    try:
        pods = _k8s.list_pods(namespace=namespace)
        if not pods:
            return f"No pods found in namespace '{namespace}'."
        return json.dumps({"namespace": namespace, "pods": pods}, indent=2)
    except Exception as exc:
        return f"Error listing pods in '{namespace}': {exc}"


@tool
def get_pod_events(namespace: str = "litmus", pod_name: str = "") -> str:
    """Fetch Kubernetes events for pods in a namespace.

    Useful for detecting pod deletions, OOMKills, restarts, and scheduling failures.
    Leave pod_name empty to get all events in the namespace.

    Args:
        namespace: The Kubernetes namespace to query.
        pod_name:  Optional pod name to filter events (empty = all pods).
    """
    try:
        events = _k8s.get_pod_events(
            namespace=namespace,
            pod_name=pod_name or None,
        )
        if not events:
            label = f"pod '{pod_name}'" if pod_name else f"namespace '{namespace}'"
            return f"No events found for {label}."
        return json.dumps({"namespace": namespace, "pod": pod_name or "all", "events": events}, indent=2)
    except Exception as exc:
        return f"Error fetching events: {exc}"


@tool
def get_pod_logs(
    namespace: str = "litmus",
    pod_name: str = "",
    container: str = "",
    tail_lines: int = 100,
) -> str:
    """Retrieve the last N lines of logs from a Kubernetes pod container.

    Args:
        namespace:  The Kubernetes namespace.
        pod_name:   Name of the pod to fetch logs from.
        container:  Container name (leave empty for the default/only container).
        tail_lines: Number of log lines to return from the end (default: 100).
    """
    if not pod_name:
        return "Error: pod_name is required."
    try:
        logs = _k8s.get_pod_logs(
            namespace=namespace,
            pod_name=pod_name,
            container=container or None,
            tail_lines=tail_lines,
        )
        return logs or f"No logs available for pod '{pod_name}'."
    except Exception as exc:
        return f"Error fetching logs for pod '{pod_name}': {exc}"


@tool
def get_pod_resource_usage(namespace: str = "litmus") -> str:
    """Get live CPU and memory usage per pod in a namespace via the metrics-server.

    Requires metrics-server to be installed in the cluster.

    Args:
        namespace: The Kubernetes namespace to query.
    """
    try:
        usage = _k8s.get_pod_resource_usage(namespace=namespace)
        if not usage:
            return f"No resource usage data found for namespace '{namespace}'."
        return json.dumps({"namespace": namespace, "pod_metrics": usage}, indent=2)
    except Exception as exc:
        return f"Error fetching resource usage: {exc}"


# ── Export (ready for Observer Agent) ────────────────────────────────────────

observer_tools = [
    list_pods,
    get_pod_events,
    get_pod_logs,
    get_pod_resource_usage,
]

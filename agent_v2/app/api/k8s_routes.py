"""FastAPI routes for Kubernetes observation.

Temporary API for validating the K8s observation layer before
integrating it with the Observer Agent.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.k8s_client import K8sClient
from services.observer_service import ObserverService

k8s_router = APIRouter()

# Single shared clients — initialised once at import time.
# If the cluster is unreachable, individual endpoints return a 503.
try:
    _k8s = K8sClient()
    _k8s_error: str | None = None
except Exception as exc:
    _k8s = None  # type: ignore[assignment]
    _k8s_error = str(exc)

try:
    _observer = ObserverService()
    _observer_error: str | None = None
except Exception as exc:
    _observer = None  # type: ignore[assignment]
    _observer_error = str(exc)


class ObserveRequest(BaseModel):
    experiment_id: str


def _client() -> K8sClient:
    """Return the shared K8s client or raise 503 if it failed to init."""
    if _k8s is None:
        raise HTTPException(
            status_code=503,
            detail=f"Kubernetes client unavailable: {_k8s_error}",
        )
    return _k8s


# ── Routes ────────────────────────────────────────────────────────────────────

@k8s_router.get("/pods", summary="List pods in a namespace")
async def list_pods(
    namespace: str = Query(default="litmus", description="Kubernetes namespace"),
):
    """List all pods and their current phase/status."""
    try:
        pods = _client().list_pods(namespace=namespace)
        return {"namespace": namespace, "count": len(pods), "pods": pods}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@k8s_router.get("/pods/resources", summary="Pod CPU & memory usage")
async def get_pod_resource_usage(
    namespace: str = Query(default="litmus", description="Kubernetes namespace"),
):
    """Return live CPU/memory usage per pod (requires metrics-server)."""
    try:
        usage = _client().get_pod_resource_usage(namespace=namespace)
        return {"namespace": namespace, "count": len(usage), "pod_metrics": usage}
    except HTTPException:
        raise
    except RuntimeError as exc:
        # metrics-server not installed — return helpful 503 instead of 500
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@k8s_router.get("/pods/{pod_name}/events", summary="Events for a specific pod")
async def get_pod_events(
    pod_name: str,
    namespace: str = Query(default="litmus", description="Kubernetes namespace"),
):
    """Fetch Kubernetes events for a pod (deletions, OOMKills, restarts, …)."""
    try:
        events = _client().get_pod_events(namespace=namespace, pod_name=pod_name)
        return {"namespace": namespace, "pod": pod_name, "count": len(events), "events": events}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@k8s_router.get("/pods/{pod_name}/logs", summary="Logs from a pod container")
async def get_pod_logs(
    pod_name: str,
    namespace: str = Query(default="litmus", description="Kubernetes namespace"),
    container: str = Query(default="", description="Container name (empty = default container)"),
    tail: int = Query(default=100, ge=1, le=5000, description="Number of log lines to return"),
):
    """Return the last N lines of stdout/stderr from a pod container."""
    try:
        logs = _client().get_pod_logs(
            namespace=namespace,
            pod_name=pod_name,
            container=container or None,
            tail_lines=tail,
        )
        lines = logs.splitlines() if logs else []
        return {
            "namespace": namespace,
            "pod": pod_name,
            "container": container or "default",
            "tail_lines_requested": tail,
            "lines_returned": len(lines),
            "logs": lines,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@k8s_router.get("/events", summary="All events in a namespace")
async def get_namespace_events(
    namespace: str = Query(default="litmus", description="Kubernetes namespace"),
):
    """Return all Kubernetes events in a namespace (not filtered to a single pod)."""
    try:
        events = _client().get_pod_events(namespace=namespace, pod_name=None)
        return {"namespace": namespace, "count": len(events), "events": events}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@k8s_router.post("/observe", summary="Verify chaos experiment results")
async def observe_experiment(req: ObserveRequest):
    """Run full observation to correlate LitmusChaos results with Kubernetes signals."""
    if _observer is None:
        raise HTTPException(
            status_code=503,
            detail=f"Observer service unavailable: {_observer_error}",
        )
    try:
        report = _observer.observe(req.experiment_id)
        return report.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

"""LangChain tools for the Observer Agent.

These tools wrap ObserverService and K8sClient, letting the Observer Agent
verify chaos experiments and inspect cluster state autonomously.
"""

from __future__ import annotations

import json
from langchain_core.tools import tool

from services.observer_service import ObserverService
from services.k8s_client import K8sClient

# Shared instances
_observer = ObserverService()
_k8s = K8sClient()


# ── Tools ─────────────────────────────────────────────────────────────────────

@tool
def verify_experiment_run(experiment_id: str) -> str:
    """Verify whether a chaos experiment actually ran as configured.

    Fetches the latest experiment run from LitmusChaos, parses the
    experiment manifest to identify fault targets, then correlates
    against Kubernetes events to confirm chaos occurred.

    Returns a structured ObservationReport as JSON.

    Args:
        experiment_id: The LitmusChaos experiment ID to verify.
    """
    try:
        report = _observer.observe(experiment_id)
        return json.dumps(report.to_dict(), indent=2, default=str)
    except Exception as exc:
        return f"Error verifying experiment '{experiment_id}': {exc}"


@tool
def get_experiment_run_status(experiment_id: str) -> str:
    """Quick status check for the latest run of a LitmusChaos experiment.

    Returns phase, resiliency score, and fault pass/fail counts
    without performing full K8s correlation.

    Args:
        experiment_id: The LitmusChaos experiment ID.
    """
    try:
        from services.litmus_client import LitmusClient
        from config import settings
        client = LitmusClient(
            api_url=settings.litmus_api_url,
            project_id=settings.litmus_project_id,
            token=settings.litmus_access_token,
            hub_id=settings.litmus_hub_id,
        )
        data = client.get_experiment(experiment_id)
        exp = data.get("getExperiment", {}).get("experimentDetails", {})
        runs = exp.get("recentExperimentRunDetails") or []
        if not runs:
            return f"No runs found for experiment '{experiment_id}'."

        latest = runs[0]
        return json.dumps({
            "experiment_id": experiment_id,
            "experiment_name": exp.get("name"),
            "latest_run_id": latest.get("experimentRunID"),
            "phase": latest.get("phase"),
            "resiliency_score": latest.get("resiliencyScore"),
            "faults_passed": latest.get("faultsPassed"),
            "faults_failed": latest.get("faultsFailed"),
            "faults_awaited": latest.get("faultsAwaited"),
            "total_faults": latest.get("totalFaults"),
            "updated_at": latest.get("updatedAt"),
        }, indent=2)
    except Exception as exc:
        return f"Error fetching status for experiment '{experiment_id}': {exc}"


@tool
def get_chaos_signals(namespace: str, fault_type: str = "") -> str:
    """Scan Kubernetes events in a namespace for chaos-related signals.

    Useful for checking if any chaos effects are visible without knowing
    the specific experiment ID.

    Args:
        namespace:  Kubernetes namespace to scan (e.g. 'chaos-ns').
        fault_type: Optional fault type to focus the signal search
                    (e.g. 'pod-delete', 'pod-cpu-hog', 'pod-memory-hog').
                    Leave empty to return all warning events.
    """
    from services.observer_service import get_fault_signals, _DEFAULT_SIGNALS
    try:
        events = _k8s.get_pod_events(namespace=namespace)
        target_reasons = set(get_fault_signals(fault_type) if fault_type else _DEFAULT_SIGNALS)

        if fault_type:
            filtered = [e for e in events if e.get("reason") in target_reasons]
        else:
            # Return Warning events only when no fault type given
            filtered = [e for e in events if e.get("type") == "Warning"]

        return json.dumps({
            "namespace": namespace,
            "fault_type": fault_type or "all-warnings",
            "signal_count": len(filtered),
            "signals": filtered[:20],  # cap at 20
        }, indent=2, default=str)
    except Exception as exc:
        return f"Error scanning chaos signals in '{namespace}': {exc}"


# ── Export ────────────────────────────────────────────────────────────────────

observer_tools = [
    verify_experiment_run,
    get_experiment_run_status,
    get_chaos_signals,
]

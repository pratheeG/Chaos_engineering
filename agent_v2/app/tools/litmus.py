"""LangChain tools that wrap the LitmusChaos GraphQL API (Planner Agent).

Reuses the real LitmusClient from services for live experiment/hub lookups.
Additionally includes a mocked Kubernetes deployment lister.
"""

from __future__ import annotations

import json
from langchain_core.tools import tool

from config import settings
from services.litmus_client import LitmusClient


_client = LitmusClient(
    api_url=settings.litmus_api_url,
    project_id=settings.litmus_project_id,
    token=settings.litmus_access_token,
    hub_id=settings.litmus_hub_id
)


# ── LitmusChaos Tools ─────────────────────────────────────────────────────────

@tool
def list_experiments() -> str:
    """List all chaos experiments configured in the LitmusChaos project.
    Use this to check if an experiment already matches the user's goal."""
    try:
        data = _client.list_experiments()
        result = data.get("listExperiment", {})
        experiments = result.get("experiments", [])
        if not experiments:
            return "No experiments found in the project."

        lines = [f"Total experiments: {result.get('totalNoOfExperiments', len(experiments))}\n"]
        for exp in experiments:
            recent = exp.get("recentExperimentRunDetails") or []
            last_run = recent[0] if recent else {}
            infra = exp.get("infra") or {}
            lines.append(
                f"• {exp['name']}\n"
                f"  ID: {exp['experimentID']}\n"
                f"  Description: {exp.get('description', 'N/A')}\n"
                f"  Tags: {', '.join(exp.get('tags') or [])}\n"
                f"  Infra: {infra.get('name', 'N/A')}\n"
                f"  Last Run Phase: {last_run.get('phase', 'N/A')}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error listing experiments: {e}"


@tool
def get_hub_faults(goal: str) -> str:
    """Returns available chaos fault types from the Chaos Hub that are relevant to the user's goal.
    
    Args:
        goal: The chaos engineering goal described by the user.
    """
    data = _client.get_hub_faults()
    result = data.get("listChaosFaults", [])

    hub_faults = next((item for item in result if item["spec"]["displayName"] == "Kubernetes"), None)
    if not hub_faults:
        return "No Chaos faults found in the project."
    return hub_faults


# ── Kubernetes Tool (Mocked) ──────────────────────────────────────────────────

@tool
def list_kubernetes_deployments(namespace: str = "default") -> str:
    """Lists available Kubernetes deployments in the given namespace.
    Use this to identify which services/deployments can be targeted for chaos.
    
    Args:
        namespace: The Kubernetes namespace to list deployments from.
    """
    # Mocked – replace with real kubernetes Python client call when in-cluster.
    deployments = ["chaos-backend", "chaos-frontend"]
    return json.dumps({
        "namespace": namespace,
        "deployments": deployments,
    })


@tool
def list_probes() -> str:
    """List all probes configured in the LitmusChaos project.
    Use this to identify which probes can be evaluated during chaos experiments.
    Returns probe names, infrastructure type, and description."""
    try:
        data = _client.list_probes()
        probes = data.get("listProbes", [])
        if not probes:
            return "No probes found in the project."

        lines = [f"Total probes: {len(probes)}\n"]
        for p in probes:
            lines.append(
                f"• {p['name']}\n"
                f"  Type: {p.get('type', 'N/A')}\n"
                f"  Infra Type: {p.get('infrastructureType', 'N/A')}\n"
                f"  Description: {p.get('description', '-')}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error listing probes: {e}"


@tool
def create_experiment(manifest_json_str: str) -> str:
    """Create a new chaos experiment using a JSON string representing the SaveChaosExperimentRequest.
    
    Args:
        manifest_json_str: The full JSON representation of the `SaveChaosExperimentRequest`.
    """
    try:
        request = json.loads(manifest_json_str)
        data = _client.save_experiment(request)
        return f"Experiment created successfully: {data.get('saveChaosExperiment', 'Unknown Response')}"
    except Exception as e:
        print('Error creating experiment: ', e)
        return f"Error creating experiment: {e}"


@tool
def run_experiment(experiment_id: str) -> str:
    """Run (trigger) an existing chaos experiment by its experiment ID.
    
    Args:
        experiment_id: The unique ID of the experiment to run.
    """
    try:
        data = _client.run_experiment(experiment_id)
        notify_id = data.get("runChaosExperiment", {}).get("notifyID", "unknown")
        return (
            f"Experiment triggered successfully!\n"
            f"Experiment ID: {experiment_id}\n"
            f"Notification ID: {notify_id}"
        )
    except Exception as e:
        return f"Error running experiment: {e}"


# ── Export ────────────────────────────────────────────────────────────────────

planner_tools = [
    list_experiments,
    get_hub_faults,
    list_kubernetes_deployments,
    list_probes,
]

executor_tools = [
    list_experiments,
    create_experiment,
    run_experiment,
]

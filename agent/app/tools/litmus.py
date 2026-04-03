"""LangChain tools that wrap the LitmusChaos GraphQL API."""

from __future__ import annotations

import json
from langchain_core.tools import tool

from config import settings
from services.litmus_client import LitmusClient

_client = LitmusClient(
    api_url=settings.litmus_api_url,
    project_id=settings.litmus_project_id,
    token=settings.litmus_access_token,
)


@tool
def list_experiments() -> str:
    """List all chaos experiments configured in the LitmusChaos project.
    Returns experiment names, IDs, infrastructure, and recent run details."""
    try:
        print("Fetching experiments from LitmusChaos...")
        data = _client.list_experiments()
        result = data.get("listExperiment", {})
        experiments = result.get("experiments", [])
        if not experiments:
            return "No experiments found in the project."

        lines = [f"Total experiments: {result.get('totalNoOfExperiments', len(experiments))}\n"]
        for exp in experiments:
            recent = exp.get("recentExperimentRunDetails") or []
            print('recent ', recent)
            last_run = recent[0] if recent else {}
            infra = exp.get("infra") or {}
            lines.append(
                f"• {exp['name']}\n"
                f"  ID: {exp['experimentID']}\n"
                f"  Type: {exp.get('experimentType', 'N/A')}\n"
                f"  Infra: {infra.get('name', 'N/A')}\n"
                f"  Last Run Phase: {last_run.get('phase', 'N/A')} | "
                f"  Last Run At: {last_run.get('updatedAt', 'N/A')} | "
                f"  Last Run Id: {last_run.get('experimentRunID', 'N/A')} | "
                f"  Total Runs: {len(recent)} | "
                f"Resiliency: {last_run.get('resiliencyScore', 'N/A')}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error listing experiments: {e}"


@tool
def list_environments() -> str:
    """List all environments registered in the LitmusChaos project.
    Returns environment names, IDs, types, and connected infrastructure."""
    try:
        data = _client.list_environments()
        result = data.get("listEnvironments", {})
        envs = result.get("environments", [])
        if not envs:
            return "No environments found in the project."

        lines = [f"Total environments: {result.get('totalNoOfEnvironments', len(envs))}\n"]
        for env in envs:
            infra_ids = env.get("infraIDs") or []
            lines.append(
                f"• {env['name']}\n"
                f"  ID: {env['environmentID']}\n"
                f"  Type: {env.get('type', 'N/A')}\n"
                f"  Description: {env.get('description', '-')}\n"
                f"  Connected Infra: {', '.join(infra_ids) if infra_ids else 'None'}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error listing environments: {e}"


@tool
def list_probes() -> str:
    """List all probes configured in the LitmusChaos project.
    Returns probe names, types, infrastructure type, and recent execution status."""
    try:
        data = _client.list_probes()
        print("Received probe data:", json.dumps(data, indent=2))
        probes = data.get("listProbes", [])
        if not probes:
            return "No probes found in the project."

        lines = [f"Total probes: {len(probes)}\n"]
        for p in probes:
            recent = p.get("recentExecutions") or []
            last_verdict = "N/A"
            if recent and recent[0].get("status"):
                last_verdict = recent[0]["status"].get("verdict", "N/A")
            lines.append(
                f"• {p['name']}\n"
                f"  Type: {p.get('type', 'N/A')}\n"
                f"  Infra Type: {p.get('infrastructureType', 'N/A')}\n"
                f"  Description: {p.get('description', '-')}\n"
                f"  Last Verdict: {last_verdict}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error listing probes: {e}"


@tool
def run_experiment(experiment_id: str) -> str:
    """Run (trigger) an existing chaos experiment by its experiment ID.
    Use list_experiments first to find the ID.

    Args:
        experiment_id: The unique ID of the experiment to run.
    """
    try:
        data = _client.run_experiment(experiment_id)
        notify_id = data.get("runChaosExperiment", {}).get("notifyID", "unknown")
        return (
            f"Experiment triggered successfully!\n"
            f"Experiment ID: {experiment_id}\n"
            f"Notification ID: {notify_id}\n"
            f"The experiment is now running. Use the LitmusChaos dashboard to monitor progress."
        )
    except Exception as e:
        return f"Error running experiment: {e}"


@tool
def get_experiment_run_status(experiment_run_id: str) -> str:
    """Get the status and details of a specific experiment run.

    Args:
        experiment_run_id: The unique ID of the experiment run to check.
    """
    try:
        data = _client.get_experiment_run(experiment_run_id)
        run = data.get("getExperimentRun", {})
        infra = run.get("infra") or {}
        return (
            f"Experiment Run: {run.get('experimentName', 'N/A')}\n"
            f"  Run ID: {run.get('experimentRunID', 'N/A')}\n"
            f"  Experiment ID: {run.get('experimentID', 'N/A')}\n"
            f"  Phase: {run.get('phase', 'N/A')}\n"
            f"  Resiliency Score: {run.get('resiliencyScore', 'N/A')}\n"
            f"  Infra: {infra.get('name', 'N/A')}\n"
            f"  Updated: {run.get('updatedAt', 'N/A')}"
        )
    except Exception as e:
        return f"Error getting experiment run status: {e}"


# Export all tools as a list for easy binding
litmus_tools = [
    list_experiments,
    list_environments,
    list_probes,
    run_experiment,
    get_experiment_run_status,
]

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
            
            # Check if manifest exists but don't print the whole string.
            has_manifest = bool(exp.get('experimentManifest'))
            
            lines.append(
                f"• {exp['name']}\n"
                f"  ID: {exp['experimentID']}\n"
                f"  Description: {exp.get('description', 'N/A')}\n"
                f"  Weightages: {exp.get('weightages', 'N/A')}\n"
                f"  Has Manifest: {has_manifest}\n"
                f"  Tags: {', '.join(exp.get('tags') or [])}\n"
                f"  Infra Name: {infra.get('name', 'N/A')}\n"
                f"  Infra ID: {infra.get('infraID', 'N/A')}\n"
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
        
    faults = hub_faults.get("spec", {}).get("faults", [])
    if not faults:
        return "No faults found in the Kubernetes category."
        
    lines = [f"Total Kubernetes Faults: {len(faults)}\n"]
    # Limit number of characters broadly or return names and descriptions
    for f in faults:
        name = f.get("name", "Unknown")
        desc = f.get("description", "-")
        lines.append(f"• {name}: {desc[:100]}...") # truncate description to keep tokens low
        
    return "\n".join(lines)


# ── Kubernetes Tool (Mocked) ──────────────────────────────────────────────────

@tool
def list_kubernetes_deployments(namespace: str = "chaos-ns") -> str:
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


import yaml
import uuid
from config import settings
from tools.yaml_builder import SaveExperimentInput, get_cached_workflow_yaml

@tool(args_schema=SaveExperimentInput)
def save_experiment(
    name: str,
    desc: str,
    tags: list[str],
    experiment_name: str,
) -> str:
    """Saves and registers a chaos experiment in LitmusChaos.

    Uses experiment_name to retrieve the pre-built workflow YAML from internal cache
    (stored by merge_workflow_yaml). Do NOT pass the YAML string directly.

    IMPORTANT: Call tools in this order first:
      1. generate_pod_delete_engines() - generate engine template blocks
      2. merge_workflow_yaml()          - assemble and cache the workflow
      3. validate_workflow_yaml()       - confirm VALID before saving
    Only call this tool after validate_workflow_yaml() returns a VALID result.

    Args:
        name:            Experiment name shown in LitmusChaos UI.
        desc:            Human-readable description.
        tags:            List of tag strings.
        experiment_name: The cache key from merge_workflow_yaml (same as the workflow name).
    """
    try:
        if not name or name.strip() == "":
            name = f"chaos-exp-{str(uuid.uuid4())[:8]}"

        # Retrieve YAML from cache — never accept it as a direct parameter
        workflow_yaml = get_cached_workflow_yaml(experiment_name)
        if not workflow_yaml:
            return (
                f"Error: No cached workflow found for experiment_name='{experiment_name}'. "
                "Call merge_workflow_yaml() and validate_workflow_yaml() first."
            )

        try:
            workflow_dict = yaml.safe_load(workflow_yaml)
        except yaml.YAMLError as exc:
            return f"Error: Cached workflow YAML could not be parsed - {exc}."

        manifest_json_str = json.dumps(workflow_dict)

        infra_id = settings.litmus_infra_id
        if not infra_id:
            return "Error: LITMUS_INFRA_ID is not set in the .env file."

        request_payload = {
            "id": str(uuid.uuid4()),
            "name": name,
            "description": desc,
            "tags": tags,
            "infraID": infra_id,
            "manifest": manifest_json_str,
        }

        print(f"Creating experiment '{name}' on infra {infra_id}")
        data = _client.save_experiment(request_payload)
        return f"Experiment created successfully: {data.get('saveChaosExperiment', 'Unknown Response')}"
    except Exception as e:
        print("Error creating experiment:", e)
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

from tools.yaml_builder import yaml_builder_tools

executor_tools = [
    list_experiments,
    *yaml_builder_tools,   # generate_pod_delete_engines, merge_workflow_yaml, validate_workflow_yaml
    save_experiment,
    run_experiment,
]

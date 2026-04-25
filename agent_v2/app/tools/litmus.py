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
import os
from app.config import settings

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fault_configs")

@tool
def save_experiment(
    name: str, 
    desc: str, 
    tags: list[str], 
    template_file: str,
    target_namespace: str,
    app_label: str,
    target_container: str,
    chaos_duration: str,
    probe_name: str = ""
) -> str:
    """Creates a chaos experiment by injecting target parameters into a base template.
    
    Args:
        name: Name of the experiment (e.g. 'pod-delete-chaos')
        desc: Description of the experiment
        tags: List of tags
        template_file: Name of the YAML file in fault_configs (e.g. 'pod-delete.yaml')
        target_namespace: Usually 'chaos-ns'
        app_label: e.g. 'app=chaos-backend'
        target_container: Name of the container to target
        chaos_duration: Duration in seconds, e.g. '60'
        probe_name: Name of a probe to attach (optional, leave empty if none)
    """
    try:
        path = os.path.join(CONFIG_DIR, template_file)
        if not os.path.exists(path):
            return f"Error: Template {template_file} not found."
            
        with open(path, "r") as f:
            manifest_str = f.read()
            
        # Fallbacks to ensure the GraphQL request doesn't bounce empty names
        if not name or name.strip() == "":
            uid_str = str(uuid.uuid4())
            name = f"chaos-exp-{uid_str[:8]}"
            
        # Perform simple targeted string replacements on the template
        manifest_str = manifest_str.replace("{{EXPERIMENT_NAME}}", name)
        manifest_str = manifest_str.replace("{{TARGET_NAMESPACE}}", target_namespace)
        manifest_str = manifest_str.replace("{{TARGET_APP_LABEL}}", app_label)
        manifest_str = manifest_str.replace("{{TARGET_CONTAINER}}", target_container)
        manifest_str = manifest_str.replace("{{TOTAL_CHAOS_DURATION}}", chaos_duration)
        
        # Format the probe JSON array if provided
        if probe_name:
            probe_json_str = '[{"name":"' + probe_name + '","mode":"Continuous"}]'
            manifest_str = manifest_str.replace("{{PROBE_REF}}", probe_json_str)
        else:
            manifest_str = manifest_str.replace("{{PROBE_REF}}", '[]')
            
        manifest_str = manifest_str.replace("{{workflow.parameters.adminModeNamespace}}", "litmus")

        # Load the YAML safely
        workflow_dict = yaml.safe_load(manifest_str)

        manifest_json_str = json.dumps(workflow_dict)

        # Read infra ID from environment config — never requires the agent to look it up
        infra_id = settings.litmus_infra_id
        if not infra_id:
            return "Error: LITMUS_INFRA_ID is not set in the .env file."

        request_payload = {
            "id": str(uuid.uuid4()),
            "name": name,
            "description": desc,
            "tags": tags,
            "infraID": infra_id,
            "manifest": manifest_json_str
        }

        print(f"Creating experiment {name} on infra {infra_id} using {template_file}")
        data = _client.save_experiment(request_payload)
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
    save_experiment,
    run_experiment,
]

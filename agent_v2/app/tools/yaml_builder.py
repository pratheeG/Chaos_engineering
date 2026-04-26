"""Tools for building, merging, and validating pod-delete Argo Workflow YAMLs dynamically.

Key design principle: Large YAML strings are NEVER passed as tool arguments.
merge_workflow_yaml() stores the assembled workflow in an in-process cache keyed
by experiment_name. Downstream tools (validate, save) look up by that key.
This prevents the LLM from having to re-serialize multi-KB YAML blobs as JSON strings,
which causes 'Failed to parse tool call arguments as JSON' errors from the API.

Three tools are exposed:

1. generate_pod_delete_engines  – renders one ChaosEngine template block per deployment
2. merge_workflow_yaml          – assembles the full workflow and caches it by experiment_name
3. validate_workflow_yaml       – validates the cached workflow by experiment_name key
"""

from __future__ import annotations

import os
import json
from typing import Any, List, Optional

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from langchain_core.tools import tool
from pydantic import BaseModel, Field

# ── Paths ─────────────────────────────────────────────────────────────────────

_CONFIG_DIR   = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fault_configs")
_INSTALL_FILE = os.path.join(_CONFIG_DIR, "pod-delete-install.yaml")
_CLEANUP_FILE = os.path.join(_CONFIG_DIR, "pod-delete-cleanup.yaml")
_ENGINE_TMPL  = "pod-delete-engine.yaml.j2"

_jinja_env = Environment(
    loader=FileSystemLoader(_CONFIG_DIR),
    undefined=StrictUndefined,
    keep_trailing_newline=True,
)

# ── In-process workflow cache ──────────────────────────────────────────────────
# Key: experiment_name (str)  →  Value: assembled workflow YAML (str)
# This avoids passing large YAML strings as tool arguments to the LLM.
_workflow_cache: dict[str, str] = {}


def _strip_comments(text: str) -> str:
    """Strip comment lines (starting with #) from a YAML text block."""
    lines = [line for line in text.splitlines() if not line.strip().startswith("#")]
    return "\n".join(lines).strip()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class DeploymentConfig(BaseModel):
    """Config for a single deployment target in a pod-delete chaos experiment."""
    name: str = Field(description="Deployment name, e.g. 'chaos-backend'")
    target_namespace: str = Field(description="Kubernetes namespace, e.g. 'chaos-ns'")
    app_label: str = Field(description="Label selector, e.g. 'app=chaos-backend'")
    target_container: str = Field(description="Container name to target, e.g. 'backend'")
    chaos_duration: str = Field(description="Fault duration in seconds as a string, e.g. '60'")
    probe_name: Optional[str] = Field(
        default="",
        description="LitmusChaos probe name to attach, or empty string for no probe"
    )


class GenerateEnginesInput(BaseModel):
    """Input for generate_pod_delete_engines."""
    deployments: List[DeploymentConfig] = Field(
        description="List of deployment configs — one ChaosEngine step is generated per entry."
    )


class MergeWorkflowInput(BaseModel):
    """Input for merge_workflow_yaml."""
    experiment_name: str = Field(
        description="Name for the Argo Workflow. Also used as the cache key for downstream tools."
    )
    engine_templates_yaml: str = Field(
        description="The engine_templates_yaml value from generate_pod_delete_engines output."
    )
    step_names: List[str] = Field(
        description="The step_names list from generate_pod_delete_engines output."
    )


class WorkflowKeyInput(BaseModel):
    """Input for tools that operate on a cached workflow (validate, save metadata)."""
    experiment_name: str = Field(
        description="The experiment_name used in merge_workflow_yaml — used to look up the cached workflow."
    )


class SaveExperimentInput(BaseModel):
    """Input for save_experiment."""
    name: str = Field(description="Experiment name shown in LitmusChaos UI.")
    desc: str = Field(description="Human-readable description of the experiment.")
    tags: List[str] = Field(description="List of tag strings for categorization.")
    experiment_name: str = Field(
        description="The experiment_name key from merge_workflow_yaml — used to retrieve the cached workflow YAML."
    )


# ── Tool 1: generate_pod_delete_engines ───────────────────────────────────────

@tool(args_schema=GenerateEnginesInput)
def generate_pod_delete_engines(deployments: List[DeploymentConfig]) -> str:
    """Renders one ChaosEngine Argo template block per deployment.

    Call this tool FIRST. It returns a JSON object with two fields:
      - engine_templates_yaml : YAML string of all rendered ChaosEngine template blocks
      - step_names            : list of step name strings (e.g. ["pod-delete-r01", "pod-delete-r02"])

    Pass BOTH fields directly to merge_workflow_yaml() using those exact field names.
    Do NOT modify, reformat, or re-serialize the returned values.
    """
    try:
        template = _jinja_env.get_template(_ENGINE_TMPL)
    except Exception as exc:
        return f"Error loading engine template '{_ENGINE_TMPL}': {exc}"

    rendered_blocks: list[str] = []
    step_names: list[str] = []

    for idx, dep in enumerate(deployments):
        engine_id = f"r{idx + 1:02d}"
        probe_name = (dep.probe_name or "").strip()
        probe_ref = (
            json.dumps([{"name": probe_name, "mode": "Continuous"}]) if probe_name else "[]"
        )
        try:
            block = template.render(
                engine_id=engine_id,
                target_namespace=dep.target_namespace,
                app_label=dep.app_label,
                target_container=dep.target_container,
                chaos_duration=str(dep.chaos_duration),
                probe_ref=probe_ref,
            )
        except Exception as exc:
            return f"Error rendering engine template for '{dep.name}': {exc}"

        rendered_blocks.append(block)
        step_names.append(f"pod-delete-{engine_id}")

    return json.dumps({
        "engine_templates_yaml": "\n".join(rendered_blocks),
        "step_names": step_names,
    })


# ── Tool 2: merge_workflow_yaml ────────────────────────────────────────────────

@tool(args_schema=MergeWorkflowInput)
def merge_workflow_yaml(
    experiment_name: str,
    engine_templates_yaml: str,
    step_names: List[str],
) -> str:
    """Assembles a complete Argo Workflow YAML from static configs and rendered engine blocks.

    Call this AFTER generate_pod_delete_engines(). Use the values from that tool's JSON output:
      - engine_templates_yaml → pass as-is
      - step_names            → pass as-is

    The assembled workflow is stored in an internal cache keyed by experiment_name.
    The YAML is NOT returned directly — downstream tools use experiment_name to look it up.
    This avoids the API error caused by passing large YAML strings as tool arguments.

    Returns: a short status JSON with the cache_key and template count.
    """
    # Load static install template
    try:
        with open(_INSTALL_FILE, "r") as fh:
            install_dict: dict = yaml.safe_load(_strip_comments(fh.read()))
    except Exception as exc:
        return f"Error loading install template: {exc}"

    # Load static cleanup template
    try:
        with open(_CLEANUP_FILE, "r") as fh:
            cleanup_dict: dict = yaml.safe_load(_strip_comments(fh.read()))
    except Exception as exc:
        return f"Error loading cleanup template: {exc}"

    # Parse rendered engine blocks
    engine_body = _strip_comments(engine_templates_yaml)
    try:
        engine_dicts = yaml.safe_load(engine_body)
        if not isinstance(engine_dicts, list):
            engine_dicts = [engine_dicts]
    except Exception as exc:
        return f"Error parsing rendered engine templates: {exc}"

    # Build sequential steps: install -> r01 -> r02 -> ... -> cleanup
    steps: list[list[dict]] = [
        [{"name": "install-chaos-faults", "template": "install-chaos-faults"}]
    ]
    for step_name in step_names:
        steps.append([{"name": step_name, "template": step_name}])
    steps.append([{"name": "cleanup-chaos-resources", "template": "cleanup-chaos-resources"}])

    all_templates: list[dict] = [
        {"name": "pod-delete", "steps": steps},
        install_dict,
        *engine_dicts,
        cleanup_dict,
    ]

    workflow: dict = {
        "kind": "Workflow",
        "apiVersion": "argoproj.io/v1alpha1",
        "metadata": {"name": experiment_name, "namespace": "litmus"},
        "spec": {
            "templates": all_templates,
            "entrypoint": "pod-delete",
            "arguments": {
                "parameters": [{"name": "adminModeNamespace", "value": "litmus"}]
            },
            "serviceAccountName": "argo-chaos",
            "securityContext": {"runAsUser": 1000, "runAsNonRoot": True},
        },
    }

    workflow_yaml = yaml.dump(
        workflow, default_flow_style=False, allow_unicode=True, sort_keys=False
    )

    # Store in cache — do NOT return the YAML to the LLM
    _workflow_cache[experiment_name] = workflow_yaml

    return json.dumps({
        "status": "success",
        "cache_key": experiment_name,
        "template_count": len(all_templates),
        "step_count": len(step_names),
        "next_step": (
            f"Call validate_workflow_yaml with experiment_name='{experiment_name}' "
            "to validate, then save_experiment to submit."
        ),
    })


# ── Tool 3: validate_workflow_yaml ─────────────────────────────────────────────

@tool(args_schema=WorkflowKeyInput)
def validate_workflow_yaml(experiment_name: str) -> str:
    """Validates the assembled Argo Workflow for an experiment before submitting to LitmusChaos.

    Uses experiment_name to look up the workflow from internal cache (set by merge_workflow_yaml).
    Does NOT require the YAML string as input — never pass raw YAML to this tool.

    Checks performed:
    1. YAML is parseable.
    2. kind == 'Workflow', apiVersion, metadata.name, spec.entrypoint present.
    3. spec.templates is a non-empty list.
    4. Every template has a 'container' or 'steps' block.
    5. All step template references resolve to declared templates.
    6. At least one ChaosEngine template (name starts with 'pod-delete-r') exists.
    7. install-chaos-faults and cleanup-chaos-resources are both present.

    Returns "VALID: ..." on success or "INVALID: ..." with itemized errors on failure.
    Only call save_experiment() after receiving a VALID result.
    """
    workflow_yaml = _workflow_cache.get(experiment_name)
    if not workflow_yaml:
        return (
            f"Error: No cached workflow found for experiment_name='{experiment_name}'. "
            "Call merge_workflow_yaml() first."
        )

    errors: list[str] = []

    try:
        doc: dict[str, Any] = yaml.safe_load(workflow_yaml)
    except yaml.YAMLError as exc:
        return f"INVALID: YAML parse error: {exc}"

    if not isinstance(doc, dict):
        return "INVALID: YAML did not produce a mapping at the top level."

    # Top-level fields
    if doc.get("kind") != "Workflow":
        errors.append(f"  - kind must be 'Workflow', got '{doc.get('kind')}'")
    if not doc.get("apiVersion"):
        errors.append("  - apiVersion is missing")
    metadata = doc.get("metadata") or {}
    if not metadata.get("name"):
        errors.append("  - metadata.name is missing or empty")
    spec = doc.get("spec") or {}
    if not spec.get("entrypoint"):
        errors.append("  - spec.entrypoint is missing")

    templates: list[dict] = spec.get("templates") or []
    if not templates:
        errors.append("  - spec.templates is empty or missing")
        return _format_report(errors)

    template_names = {t.get("name") for t in templates if isinstance(t, dict)}

    # Each template has container or steps
    for tmpl in templates:
        if not isinstance(tmpl, dict):
            continue
        tname = tmpl.get("name", "<unnamed>")
        if "container" not in tmpl and "steps" not in tmpl:
            errors.append(f"  - Template '{tname}' has neither 'container' nor 'steps'")

    # Step references resolve
    for tmpl in templates:
        if not isinstance(tmpl, dict):
            continue
        for step_group in (tmpl.get("steps") or []):
            for step in step_group:
                ref = step.get("template")
                if ref and ref not in template_names:
                    errors.append(
                        f"  - Step '{step.get('name')}' references unknown template '{ref}'"
                    )

    # At least one engine template
    engine_templates = [n for n in template_names if n and n.startswith("pod-delete-r")]
    if not engine_templates:
        errors.append("  - No ChaosEngine templates found (expected 'pod-delete-rXX')")

    # Required static templates
    for required in ("install-chaos-faults", "cleanup-chaos-resources"):
        if required not in template_names:
            errors.append(f"  - Required template '{required}' is missing")

    return _format_report(errors)


def _format_report(errors: list[str]) -> str:
    if not errors:
        return "VALID: Workflow YAML is valid - ready to submit."
    return f"INVALID: Validation failed with {len(errors)} issue(s):\n" + "\n".join(errors)


def get_cached_workflow_yaml(experiment_name: str) -> str | None:
    """Internal helper: retrieve cached workflow YAML by experiment_name."""
    return _workflow_cache.get(experiment_name)


# ── Exports ────────────────────────────────────────────────────────────────────

yaml_builder_tools = [
    generate_pod_delete_engines,
    merge_workflow_yaml,
    validate_workflow_yaml,
]

"""Tools for building, merging, and validating Argo Workflow YAMLs dynamically.

Supports a scalable architecture using a Fault Registry (fault_registry.json).
This eliminates the need to hardcode fault definitions in LLM prompts.

Key design principle: Large YAML strings are NEVER passed as tool arguments.
Each generator tool stages its rendered engine blocks in an in-process
_engine_staging_cache keyed by fault_type. merge_workflow_yaml() reads from
that cache using the fault_types list, then stores the assembled workflow in
_workflow_cache keyed by experiment_name.
"""

from __future__ import annotations

import os
import json
from typing import Any, List, Optional, Dict

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from langchain_core.tools import tool
from pydantic import BaseModel, Field

# ── Paths ─────────────────────────────────────────────────────────────────────

_BASE_DIR = os.path.dirname(os.path.dirname(__file__))
_CONFIG_DIR = os.path.join(_BASE_DIR, "fault_configs")
_REGISTRY_FILE = os.path.join(_BASE_DIR, "fault_registry.json")
_CLEANUP_FILE = os.path.join(_CONFIG_DIR, "chaos-cleanup.yaml")

_jinja_env = Environment(
    loader=FileSystemLoader(_CONFIG_DIR),
    undefined=StrictUndefined,
    keep_trailing_newline=True,
)

# ── Registry Loading ──────────────────────────────────────────────────────────

def _load_registry() -> Dict[str, Any]:
    """Load the fault registry from JSON."""
    if not os.path.exists(_REGISTRY_FILE):
        return {}
    with open(_REGISTRY_FILE, "r") as f:
        return json.load(f)

# ── In-process caches ──────────────────────────────────────────────────────────
# Staging cache  — Key: fault_type → {"templates_yaml": str, "step_names": list[str]}
_engine_staging_cache: dict[str, dict] = {}

# Workflow cache — Key: experiment_name → assembled workflow YAML (str)
_workflow_cache: dict[str, str] = {}


def _strip_comments(text: str) -> str:
    """Strip comment lines (starting with #) from a YAML text block."""
    lines = [line for line in text.splitlines() if not line.strip().startswith("#")]
    return "\n".join(lines).strip()


def _build_probe_ref(probe_name: Optional[str]) -> str:
    name = (probe_name or "").strip()
    return json.dumps([{"name": name, "mode": "Continuous"}]) if name else "[]"


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class GenerateChaosEnginesInput(BaseModel):
    """Input for generate_chaos_engines."""
    fault_type: str = Field(description="The type of fault to generate, e.g. 'pod-delete' or 'pod-cpu-hog'.")
    deployments: List[Dict[str, Any]] = Field(
        description=(
            "List of deployment configs. Each dict should contain parameters required by the fault "
            "(e.g. name, target_namespace, app_label, target_container, chaos_duration, etc.)."
        )
    )

class MergeWorkflowInput(BaseModel):
    """Input for merge_workflow_yaml."""
    experiment_name: str = Field(
        description="Name for the Argo Workflow. Also used as the cache key for downstream tools."
    )
    fault_types: List[str] = Field(
        description=(
            "Fault types to include. Must match generator tools already called. "
            "Example: ['pod-delete', 'pod-cpu-hog'] for a mixed experiment."
        )
    )

class WorkflowKeyInput(BaseModel):
    """Input for tools that operate on a cached workflow (validate, save)."""
    experiment_name: str = Field(
        description="The experiment_name used in merge_workflow_yaml."
    )

class SaveExperimentInput(BaseModel):
    """Input for save_experiment."""
    name: str = Field(description="Experiment name shown in LitmusChaos UI.")
    desc: str = Field(description="Human-readable description of the experiment.")
    tags: List[str] = Field(description="List of tag strings for categorization.")
    experiment_name: str = Field(
        description="The experiment_name key from merge_workflow_yaml — used to retrieve cached YAML."
    )

# ── Discovery Tools ──────────────────────────────────────────────────────────

@tool
def get_fault_catalog() -> str:
    """Returns a compact list of all supported fault types with one-line descriptions.
    The planner calls this first to discover what faults are available.
    """
    registry = _load_registry()
    catalog = [
        {"name": name, "description": data.get("description", "No description available")}
        for name, data in registry.items()
    ]
    return json.dumps({"faults": catalog}, indent=2)

@tool
def get_fault_schema(fault_type: str) -> str:
    """Returns the full parameter schema for a specific fault type.
    The planner calls this after selecting a fault to know what parameters to collect.
    """
    registry = _load_registry()
    if fault_type not in registry:
        return json.dumps({"error": f"Fault type '{fault_type}' not found in registry."})
    
    return json.dumps({
        "fault_type": fault_type,
        "description": registry[fault_type].get("description"),
        "parameters": registry[fault_type].get("parameters")
    }, indent=2)

# ── Generator Tool ───────────────────────────────────────────────────────────

@tool(args_schema=GenerateChaosEnginesInput)
def generate_chaos_engines(fault_type: str, deployments: List[Dict[str, Any]]) -> str:
    """Renders ChaosEngine Argo template blocks for any supported fault type and stages it internally.

    Call this for all deployments that should receive a specific fault.
    Output is stored in an internal staging cache — do NOT pass YAML between tools.

    Returns compact JSON status.
    """
    registry = _load_registry()
    if fault_type not in registry:
        return f"Error: Fault type '{fault_type}' not found in registry."

    fault_data = registry[fault_type]
    template_file = fault_data.get("template")
    
    try:
        template = _jinja_env.get_template(template_file)
    except Exception as exc:
        return f"Error loading engine template '{template_file}': {exc}"

    rendered_blocks: list[str] = []
    step_names: list[str] = []

    # Build a defaults map from the registry so optional params are never undefined
    param_defaults: dict[str, str] = {}
    for param_name, param_meta in fault_data.get("parameters", {}).items():
        if not param_meta.get("required", True) and "default" in param_meta:
            param_defaults[param_name] = str(param_meta["default"])

    for idx, dep in enumerate(deployments):
        engine_id = f"r{idx + 1:02d}"

        # Start with registry defaults, then overlay what the LLM provided
        context = {**param_defaults, **dep}
        context["engine_id"] = engine_id

        # Build probe_ref from probe_name if given; default to empty list
        if "probe_name" in context:
            context["probe_ref"] = _build_probe_ref(context.get("probe_name"))
        elif "probe_ref" not in context:
            context["probe_ref"] = "[]"

        # Validate that all required parameters are present before rendering
        missing_required = [
            p for p, meta in fault_data.get("parameters", {}).items()
            if meta.get("required", True) and p not in context
        ]
        if missing_required:
            return (
                f"Error: Missing required parameters for '{dep.get('name', 'unknown')}': "
                f"{missing_required}. Check get_fault_schema('{fault_type}') for the full list."
            )

        try:
            block = template.render(**context)
        except Exception as exc:
            return f"Error rendering template for '{dep.get('name', 'unknown')}': {exc}"

        rendered_blocks.append(block)
        step_names.append(f"{fault_type}-{engine_id}")

    _engine_staging_cache[fault_type] = {
        "templates_yaml": "\n".join(rendered_blocks),
        "step_names": step_names,
    }

    print("\n\n\nstaged", json.dumps({
        "status": "staged",
        "fault_type": fault_type,
        "step_names": step_names,
        "next_step": "Call merge_workflow_yaml() after generating all required engine blocks."
    }))
    return json.dumps({
        "status": "staged",
        "fault_type": fault_type,
        "step_names": step_names,
        "next_step": "Call merge_workflow_yaml() after generating all required engine blocks."
    })

# ── Assembly Tool ────────────────────────────────────────────────────────────

@tool(args_schema=MergeWorkflowInput)
def merge_workflow_yaml(experiment_name: str, fault_types: List[str]) -> str:
    """Assembles a complete Argo Workflow YAML from staged engine blocks and static templates.

    Call this AFTER the generate_chaos_engines() tool for each fault type.
    
    The assembled workflow is cached internally by experiment_name.
    """
    registry = _load_registry()
    
    invalid = [ft for ft in fault_types if ft not in registry]
    if invalid:
        return f"Error: Unsupported fault_types: {invalid}. Supported: {list(registry.keys())}"

    missing = [ft for ft in fault_types if ft not in _engine_staging_cache]
    if missing:
        return f"Error: No staged engine templates for: {missing}. Call generate_chaos_engines(fault_type=...) first."

    # Load install templates for each requested fault type
    install_dicts: list[dict] = []
    for ft in fault_types:
        install_yaml_file = registry[ft].get("install_yaml")
        if not install_yaml_file:
            continue
            
        install_path = os.path.join(_CONFIG_DIR, install_yaml_file)
        try:
            with open(install_path, "r") as fh:
                d = yaml.safe_load(_strip_comments(fh.read()))
                if d:
                    install_dicts.append(d)
        except Exception as exc:
            return f"Error loading install template for '{ft}' from '{install_path}': {exc}"

    # Load shared cleanup template
    try:
        with open(_CLEANUP_FILE, "r") as fh:
            cleanup_dict: dict = yaml.safe_load(_strip_comments(fh.read()))
    except Exception as exc:
        return f"Error loading cleanup template from '{_CLEANUP_FILE}': {exc}"

    # Collect all engine dicts and step names from staging cache
    all_engine_dicts: list[dict] = []
    all_step_names: list[str] = []
    for ft in fault_types:
        staged = _engine_staging_cache[ft]
        engine_body = _strip_comments(staged["templates_yaml"])
        try:
            engine_dicts = yaml.safe_load(engine_body)
            if not isinstance(engine_dicts, list):
                engine_dicts = [engine_dicts]
        except Exception as exc:
            return f"Error parsing staged engine templates for '{ft}': {exc}"
        all_engine_dicts.extend(engine_dicts)
        all_step_names.extend(staged["step_names"])

    # Build sequential steps: installs → engines → cleanup
    steps: list[list[dict]] = []
    for install_dict in install_dicts:
        install_name = install_dict.get("name", "install-chaos-faults")
        steps.append([{"name": install_name, "template": install_name}])
    for step_name in all_step_names:
        steps.append([{"name": step_name, "template": step_name}])
    steps.append([{"name": "cleanup-chaos-resources", "template": "cleanup-chaos-resources"}])

    # Entrypoint template name derived from fault types
    entrypoint_name = "-".join(sorted(set(fault_types)))

    all_templates: list[dict] = [
        {"name": entrypoint_name, "steps": steps},
        *install_dicts,
        *all_engine_dicts,
        cleanup_dict,
    ]

    workflow: dict = {
        "kind": "Workflow",
        "apiVersion": "argoproj.io/v1alpha1",
        "metadata": {"name": experiment_name, "namespace": "litmus"},
        "spec": {
            "templates": all_templates,
            "entrypoint": entrypoint_name,
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

    # Cache the workflow and clear consumed staging entries
    _workflow_cache[experiment_name] = workflow_yaml
    for ft in fault_types:
        _engine_staging_cache.pop(ft, None)

    return json.dumps({
        "status": "success",
        "cache_key": experiment_name,
        "fault_types": fault_types,
        "template_count": len(all_templates),
        "engine_step_count": len(all_step_names),
        "next_step": f"Call validate_workflow_yaml(experiment_name='{experiment_name}') to validate."
    })

# ── Validation Tool ──────────────────────────────────────────────────────────

@tool(args_schema=WorkflowKeyInput)
def validate_workflow_yaml(experiment_name: str) -> str:
    """Validates the assembled Argo Workflow before submitting to LitmusChaos.
    
    Uses experiment_name to look up the workflow from the internal cache.
    """
    workflow_yaml = _workflow_cache.get(experiment_name)
    if not workflow_yaml:
        return f"Error: No cached workflow found for experiment_name='{experiment_name}'."

    errors: list[str] = []

    try:
        doc: dict[str, Any] = yaml.safe_load(workflow_yaml)
    except yaml.YAMLError as exc:
        return f"INVALID: YAML parse error: {exc}"

    if not isinstance(doc, dict):
        return "INVALID: YAML did not produce a mapping at the top level."

    if doc.get("kind") != "Workflow":
        errors.append(f"  - kind must be 'Workflow', got '{doc.get('kind')}'")
    
    spec = doc.get("spec") or {}
    templates: list[dict] = spec.get("templates") or []
    if not templates:
        errors.append("  - spec.templates is empty or missing")
        return _format_report(errors)

    template_names = {t.get("name") for t in templates if isinstance(t, dict)}

    if "cleanup-chaos-resources" not in template_names:
        errors.append("  - Required template 'cleanup-chaos-resources' is missing")

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
    get_fault_catalog,
    get_fault_schema,
    generate_chaos_engines,
    merge_workflow_yaml,
    validate_workflow_yaml,
]

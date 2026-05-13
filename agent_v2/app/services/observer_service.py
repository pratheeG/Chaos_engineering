"""Observer Service — correlates LitmusChaos run data with Kubernetes signals.

Given an experiment_id, this service:
1. Fetches the latest run from LitmusChaos (phase, resiliency score, manifest).
2. Parses the manifest to extract fault types, target namespace, and app_label.
3. Queries Kubernetes events in the target namespace.
4. Applies fault-specific signal detection to confirm chaos occurred.
5. Returns a structured ObservationReport.
"""

from __future__ import annotations

import json
import re
import yaml
from dataclasses import dataclass, field, asdict
from typing import Any

from services.litmus_client import LitmusClient
from services.k8s_client import K8sClient
from services.prometheus_client import PrometheusClient
from config import settings
from datetime import datetime, timezone


# ── K8s event reasons that indicate each fault type ──────────────────────────

import os

_DEFAULT_SIGNALS = ["Killing", "OOMKilling", "Started", "Evicted", "BackOff"]

def get_fault_signals(fault_type: str) -> list[str]:
    """Read expected K8s signals for a fault type from the registry."""
    registry_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fault_registry.json")
    try:
        with open(registry_path, "r") as f:
            registry = json.load(f)
        fault_data = registry.get(fault_type, {})
        return fault_data.get("k8s_signals", _DEFAULT_SIGNALS)
    except Exception:
        return _DEFAULT_SIGNALS


# ── Report dataclasses ────────────────────────────────────────────────────────

@dataclass
class FaultObservation:
    fault_type: str
    target_namespace: str
    app_label: str
    expected_signals: list[str]
    k8s_signals_found: list[str]
    matching_events: list[dict]
    chaos_confirmed: bool
    metrics: dict[str, Any] = field(default_factory=dict)
    note: str = ""


@dataclass
class ObservationReport:
    experiment_id: str
    experiment_name: str
    run_id: str
    litmus_phase: str
    litmus_resiliency_score: float | None
    faults_passed: int
    faults_failed: int
    faults_awaited: int
    total_faults: int
    faults: list[FaultObservation]
    overall_verdict: str          # RUNNING | CONFIRMED | PARTIAL | NOT_CONFIRMED | UNKNOWN
    summary: str

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# ── Manifest parsing ──────────────────────────────────────────────────────────

def _parse_manifest(manifest_json_or_yaml: str) -> list[dict[str, Any]]:
    """Extract fault targets from an Argo Workflow manifest.

    Returns a list of dicts: [{fault_type, target_namespace, app_label}, ...]
    """
    targets: list[dict[str, Any]] = []
    if not manifest_json_or_yaml:
        return targets

    # The manifest is stored as a JSON string in LitmusChaos
    try:
        doc = json.loads(manifest_json_or_yaml)
    except (json.JSONDecodeError, TypeError):
        try:
            doc = yaml.safe_load(manifest_json_or_yaml)
        except Exception:
            return targets

    if not isinstance(doc, dict):
        return targets

    templates: list[dict] = doc.get("spec", {}).get("templates", [])
    for tmpl in templates:
        inputs = tmpl.get("inputs", {})
        for artifact in inputs.get("artifacts", []):
            raw_data = artifact.get("raw", {}).get("data", "")
            if not raw_data:
                continue
            try:
                engine: dict = yaml.safe_load(raw_data)
            except Exception:
                continue
            if not isinstance(engine, dict) or engine.get("kind") != "ChaosEngine":
                continue

            spec = engine.get("spec", {})
            appinfo = spec.get("appinfo", {})
            for exp in spec.get("experiments", []):
                fault_type = exp.get("name", "unknown")
                targets.append({
                    "fault_type": fault_type,
                    "target_namespace": appinfo.get("appns", "litmus"),
                    "app_label": appinfo.get("applabel", ""),
                })

    return targets


# ── K8s signal detection ──────────────────────────────────────────────────────

def _detect_signals(
    events: list[dict],
    app_label: str,
    fault_type: str,
) -> tuple[list[str], list[dict]]:
    """Filter events to those matching the app_label and return found signal reasons."""
    expected = get_fault_signals(fault_type)

    # Extract the label value from "app=chaos-backend" → "chaos-backend"
    label_value = app_label.split("=", 1)[-1].lower() if "=" in app_label else app_label.lower()

    matching: list[dict] = []
    for ev in events:
        pod_name = (ev.get("pod") or "").lower()
        reason = ev.get("reason") or ""
        if label_value and label_value not in pod_name:
            continue
        if reason in expected:
            matching.append(ev)

    found_reasons = list({ev["reason"] for ev in matching if ev.get("reason")})
    return found_reasons, matching


# ── Main correlation function ─────────────────────────────────────────────────

class ObserverService:
    def __init__(self) -> None:
        self._litmus = LitmusClient(
            api_url=settings.litmus_api_url,
            project_id=settings.litmus_project_id,
            token=settings.litmus_access_token,
            hub_id=settings.litmus_hub_id,
        )
        self._k8s = K8sClient()
        self._prom = PrometheusClient(settings.prometheus_url)

    def _analyze_metrics(self, fault_type: str, metrics: dict[str, Any]) -> tuple[bool, str]:
        """Analyze Prometheus metrics to see if chaos signals are present."""
        if not metrics:
            return False, ""

        # 1. Pod Count (Good for pod-delete, pod-kill, etc)
        pod_series = metrics.get("pod_count", [])
        if pod_series and "values" in pod_series[0]:
            values = [float(v[1]) for v in pod_series[0]["values"]]
            if values:
                min_pods = min(values)
                max_pods = max(values)
                if min_pods < max_pods:
                    return True, f"Confirmed: Pod count dropped from {int(max_pods)} to {int(min_pods)} during experiment."

        # 2. CPU Usage (Good for cpu-hog)
        cpu_series = metrics.get("cpu", [])
        if "cpu" in fault_type.lower() and cpu_series and "values" in cpu_series[0]:
            values = [float(v[1]) for v in cpu_series[0]["values"]]
            if values:
                avg = sum(values) / len(values)
                peak = max(values)
                if peak > avg * 1.5:  # 50% spike over average
                    return True, f"Confirmed: Detected a CPU spike of {peak:.2f} (avg: {avg:.2f}) via Prometheus."

        # 3. Memory Usage (Good for memory-hog)
        mem_series = metrics.get("memory", [])
        if "memory" in fault_type.lower() and mem_series and "values" in mem_series[0]:
            values = [float(v[1]) for v in mem_series[0]["values"]]
            if values:
                start_mem = values[0]
                peak_mem = max(values)
                if peak_mem > start_mem * 1.2: # 20% growth
                    return True, f"Confirmed: Detected memory growth from {start_mem/1024/1024:.1f}MB to {peak_mem/1024/1024:.1f}MB."

        return False, ""

    def _parse_litmus_time(self, time_str: str | None) -> datetime:
        """Parse Litmus timestamp string to datetime."""
        if not time_str:
            return datetime.now(timezone.utc)
        try:
            # Litmus often returns Unix timestamps as strings or floats
            return datetime.fromtimestamp(float(time_str)/1000, tz=timezone.utc)
        except (ValueError, TypeError):
            try:
                # Fallback to ISO parsing
                return datetime.fromisoformat(float(time_str)/1000, tz=timezone.utc).replace("Z", "+00:00")
            except Exception:
                return datetime.now(timezone.utc)

    def observe(self, experiment_id: str) -> ObservationReport:
        """Run full observation for the latest run of an experiment."""
        print("Observing experiment", experiment_id)
        # 1. Get latest run details (runID + notifyID)
        run_details = self._litmus.get_latest_experiment_run_details(experiment_id)
        print('run_details ', run_details)

        if not run_details:
            return ObservationReport(
                experiment_id=experiment_id,
                experiment_name="unknown",
                run_id="",
                litmus_phase="unknown",
                litmus_resiliency_score=None,
                faults_passed=0,
                faults_failed=0,
                faults_awaited=0,
                total_faults=0,
                faults=[],
                overall_verdict="UNKNOWN",
                summary="No experiment runs found for this experiment ID.",
            )

        run_id = run_details.get("experimentRunID")
        notify_id = run_details.get("notifyID")

        # 2. Get full run details
        run_data = self._litmus.get_experiment_run(run_id, notify_id=notify_id)
        run = run_data.get("getExperimentRun", {})

        phase = run.get("phase", "unknown")
        resiliency = run.get("resiliencyScore")
        faults_passed = run.get("faultsPassed") or 0
        faults_failed = run.get("faultsFailed") or 0
        faults_awaited = run.get("faultsAwaited") or 0
        total_faults = run.get("totalFaults") or 0
        exp_name = run.get("experimentName", "unknown")
        manifest_raw = run.get("experimentManifest", "")
        start_time = self._parse_litmus_time(run.get("createdAt"))
        print('start_time ', start_time)
        end_time = self._parse_litmus_time(run.get("updatedAt"))
        print('end_time ', end_time)

        # 3. Parse manifest to get fault targets
        targets = _parse_manifest(manifest_raw)

        print('targets', targets)

        # 4. Fetch K8s events per unique namespace
        namespaces = list({t["target_namespace"] for t in targets}) or ["litmus"]
        all_events: list[dict] = []
        for ns in namespaces:
            try:
                all_events.extend(self._k8s.get_pod_events(namespace=ns))
            except Exception:
                pass  # namespace may not exist — skip gracefully

        # 5. Correlate each fault target with K8s signals
        fault_observations: list[FaultObservation] = []
        for target in targets:
            expected = get_fault_signals(target["fault_type"])
            found, matching = _detect_signals(all_events, target["app_label"], target["fault_type"])
            confirmed = len(found) > 0

            # 5.b Fetch Prometheus metrics
            metrics = {}
            try:
                # Use app_label as pod prefix for prometheus query
                pod_prefix = target["app_label"].split("=", 1)[-1] if "=" in target["app_label"] else target["app_label"]
                metrics = self._prom.get_container_metrics(
                    namespace=target["target_namespace"],
                    pod_prefix=pod_prefix,
                    start=start_time,
                    end=end_time,
                )
            except Exception as e:
                print(f"Warning: Could not fetch Prometheus metrics: {e}")

            # 5.c Final confirmation logic (K8s Events OR Prometheus Metrics)
            metric_confirmed, metric_note = self._analyze_metrics(target["fault_type"], metrics)
            
            final_confirmed = confirmed or metric_confirmed
            
            note = ""
            if confirmed:
                note = "Confirmed via Kubernetes events."
            elif metric_confirmed:
                note = f"Kubernetes events expired or missing. {metric_note}"
            else:
                note = (
                    "No matching K8s events or significant Prometheus metric changes found. "
                    "Chaos may not have run, or data may have expired."
                )

            fault_observations.append(FaultObservation(
                fault_type=target["fault_type"],
                target_namespace=target["target_namespace"],
                app_label=target["app_label"],
                expected_signals=expected,
                k8s_signals_found=found,
                matching_events=matching[:10],  # cap at 10 events per fault
                chaos_confirmed=final_confirmed,
                metrics=metrics,
                note=note
            ))

        # 6. Determine overall verdict
        if phase.lower() == "running":
            verdict = "RUNNING"
            summary = (
                f"Experiment is currently running. "
                f"LitmusChaos phase: {phase}. "
                f"Faults progress: {faults_passed} passed, {faults_failed} failed, {faults_awaited} awaited."
            )
        elif not fault_observations:
            verdict = "UNKNOWN"
            summary = "Could not parse experiment manifest — no fault targets identified."
        elif all(f.chaos_confirmed for f in fault_observations):
            verdict = "CONFIRMED"
            summary = (
                f"All {len(fault_observations)} fault(s) confirmed via Kubernetes events. "
                f"LitmusChaos phase: {phase}, resiliency score: {resiliency}."
            )
        elif any(f.chaos_confirmed for f in fault_observations):
            confirmed_count = sum(1 for f in fault_observations if f.chaos_confirmed)
            verdict = "PARTIAL"
            summary = (
                f"{confirmed_count}/{len(fault_observations)} fault(s) confirmed via K8s events. "
                f"LitmusChaos phase: {phase}, resiliency score: {resiliency}."
            )
        else:
            verdict = "NOT_CONFIRMED"
            summary = (
                f"No K8s signals found for any fault. "
                f"LitmusChaos phase: {phase}. "
                "Events may have expired (TTL ~1h) or the experiment did not run successfully."
            )

        return ObservationReport(
            experiment_id=experiment_id,
            experiment_name=exp_name,
            run_id=run_id,
            litmus_phase=phase,
            litmus_resiliency_score=resiliency,
            faults_passed=faults_passed,
            faults_failed=faults_failed,
            faults_awaited=faults_awaited,
            total_faults=total_faults,
            faults=fault_observations,
            overall_verdict=verdict,
            summary=summary,
        )

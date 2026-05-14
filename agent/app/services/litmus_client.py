"""Thin synchronous wrapper around the LitmusChaos 3.x GraphQL API.
Copied from agent/app/services/litmus_client.py and kept identical.
"""

from __future__ import annotations

import httpx
from typing import Any


class LitmusClient:
    """Speaks to the LitmusChaos ChaosCenter GraphQL endpoint."""

    def __init__(self, api_url: str, project_id: str, token: str, hub_id: str) -> None:
        self._url = api_url
        self._project_id = project_id
        self._hub_id = hub_id
        self._headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

    # ── helpers ───────────────────────────────────────────────────────────────

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Synchronous GraphQL POST (keeps LangChain tools simple)."""
        try:
            resp = httpx.post(
                self._url,
                json=payload,
                headers=self._headers,
                timeout=30.0,
            )
            resp.raise_for_status()
            body = resp.json()
            if "errors" in body:
                raise RuntimeError(body["errors"])
            return body["data"]
        except httpx.RequestError as e:
            raise RuntimeError(f"Request failed: {e}")
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"HTTP error: {e}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error: {e}")

    # ── public operations ─────────────────────────────────────────────────────

    def list_experiments(self) -> dict[str, Any]:
        """Return all experiments in the project."""
        query = """
        query ListExperiment($projectID: ID!, $request: ListExperimentRequest!) {
            listExperiment(projectID: $projectID, request: $request) {
                totalNoOfExperiments
                experiments {
                    experimentID
                    experimentType
                    name
                    description
                    tags
                    weightages {
                        faultName
                        weightage
                    }
                    experimentManifest
                    infra {
                        infraID
                        name
                        environmentID
                    }
                    recentExperimentRunDetails {
                        experimentRunID
                        phase
                        resiliencyScore
                        updatedAt
                    }
                }
            }
        }
        """
        variables = {
            "projectID": self._project_id,
            "request": {
                "experimentIDs": [],
                "pagination": {"page": 0, "limit": 50},
            },
        }
        return self._post({"query": query, "variables": variables})

    def get_experiment(self, experiment_id: str) -> dict[str, Any]:
        """Return details of a specific experiment by ID."""
        query = """
        query GetExperiment($projectID: ID!, $experimentID: String!) {
            getExperiment(projectID: $projectID, experimentID: $experimentID) {
                experimentDetails {
                    experimentID
                    experimentType
                    experimentManifest
                    name
                    description
                    tags
                    infra {
                        infraID
                        name
                        environmentID
                    }
                    recentExperimentRunDetails {
                        experimentRunID
                        phase
                        resiliencyScore
                        updatedAt
                    }
                }
                averageResiliencyScore
            }
        }
        """
        variables = {
            "projectID": self._project_id,
            "experimentID": experiment_id,
        }
        return self._post({"query": query, "variables": variables})

    def run_experiment(self, experiment_id: str) -> dict[str, Any]:
        """Trigger (re-run) an existing experiment by ID."""
        query = """
        mutation RunChaosExperiment($experimentID: String!, $projectID: ID!) {
            runChaosExperiment(
                experimentID: $experimentID
                projectID: $projectID
            ) {
                notifyID
            }
        }
        """
        variables = {
            "experimentID": experiment_id,
            "projectID": self._project_id,
        }
        return self._post({"query": query, "variables": variables})
    
    def get_hub_faults(self) -> dict[str, Any]:
        """Returns all hub faults in the project"""
        query = """
        query ListChaosFaults($hubID: ID!,$projectID: ID!) {
            listChaosFaults(hubID: $hubID, projectID: $projectID) {
                apiVersion
                kind
                metadata {
                    name
                    version
                    annotations {
                        categories
                    }
                }
                spec {
                    displayName
                    categoryDescription
                    keywords
                    maturity
                    minKubeVersion
                    faults {
                        name
                        displayName
                        description 
                        plan
                    }
                    experiments
                    chaosExpCRDLink
                    platforms
                    chaosType
                }
                packageInfo {
                    packageName
                    experiments {
                        name
                        desc
                        CSV
                    }
                }
            }
        }
        """
        variables = {
            "hubID": self._hub_id,
            "projectID": self._project_id,
        }
        return self._post({"query": query, "variables": variables})
                
    def list_probes(self) -> dict[str, Any]:
        """Return all probes in the project."""
        query = """
        query ListProbes($projectID: ID!, $infrastructureType: InfrastructureType) {
            listProbes(projectID: $projectID, infrastructureType: $infrastructureType) {
                name
                type
                description
                infrastructureType
                recentExecutions {
                    status {
                        verdict
                    }
                }
                updatedAt
            }
        }
        """
        variables = {
            "projectID": self._project_id,
            "infrastructureType": "Kubernetes",
        }
        return self._post({"query": query, "variables": variables})

    def save_experiment(self, request: dict[str, Any]) -> dict[str, Any]:
        """Save/Create a chaos experiment."""
        query = """
        mutation SaveChaosExperiment($projectID: ID!, $request: SaveChaosExperimentRequest!) {
            saveChaosExperiment(
                projectID: $projectID
                request: $request
            )
        }
        """
        variables = {
            "projectID": self._project_id,
            "request": request,
        }
        return self._post({"query": query, "variables": variables})

    def get_experiment_run(self, experiment_run_id: str, notify_id: str | None = None) -> dict[str, Any]:
        """Return full details of a specific experiment run by its run ID."""
        query = """
        query GetExperimentRun($projectID: ID!, $experimentRunID: ID, $notifyID: ID) {
            getExperimentRun(projectID: $projectID, experimentRunID: $experimentRunID, notifyID: $notifyID) {
                projectID
                experimentRunID
                experimentID
                experimentName
                experimentType
                phase
                resiliencyScore
                faultsPassed
                faultsFailed
                faultsAwaited
                faultsStopped
                faultsNa
                totalFaults
                updatedAt
                createdAt
                experimentManifest
                notifyID
                infra {
                    infraID
                    name
                }
                weightages {
                    faultName
                    weightage
                }
            }
        }
        """
        variables = {
            "projectID": self._project_id,
            "experimentRunID": experiment_run_id,
            "notifyID": notify_id
        }
        return self._post({"query": query, "variables": variables})

    def list_experiment_runs(self, experiment_id: str, limit: int = 1) -> dict[str, Any]:
        """Returns list of runs for a specific experiment to get notifyID etc."""
        query = """
        query ListExperimentRun($projectID: ID!, $request: ListExperimentRunRequest!) {
            listExperimentRun(projectID: $projectID, request: $request) {
                totalNoOfExperimentRuns
                experimentRuns {
                    projectID
                    experimentRunID
                    experimentName
                    notifyID
                    resiliencyScore
                    phase
                }
            }
        }
        """
        variables = {
            "projectID": self._project_id,
            "request": {
                "experimentIDs": [experiment_id],
                "pagination": {"page": 0, "limit": limit}
            }
        }
        return self._post({"query": query, "variables": variables})

    def get_latest_experiment_run_details(self, experiment_id: str) -> dict[str, str] | None:
        """Fetch the most recent run ID and notify ID for a given experiment."""
        data = self.list_experiment_runs(experiment_id, limit=1)
        runs = data.get("listExperimentRun", {}).get("experimentRuns") or []
        if not runs:
            return None
        
        latest = runs[0]
        return {
            "experimentRunID": latest.get("experimentRunID"),
            "notifyID": latest.get("notifyID")
        }


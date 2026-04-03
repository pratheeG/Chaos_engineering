"""Thin async wrapper around the LitmusChaos 3.x GraphQL API."""

from __future__ import annotations

import httpx
from typing import Any


class LitmusClient:
    """Speaks to the LitmusChaos ChaosCenter GraphQL endpoint."""

    def __init__(self, api_url: str, project_id: str, token: str) -> None:
        self._url = api_url
        self._project_id = project_id
        self._headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

    # ── helpers ───────────────────────────────────────────────────────────

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Synchronous GraphQL POST (keeps LangChain tools simple)."""
        print(f"POSTing to LitmusChaos API at {self._url} with payload: {payload}, headers: {self._headers}")
        try:
            resp = httpx.post(
                self._url,
                json=payload,
                headers=self._headers,
                timeout=30.0,
            )
            resp.raise_for_status()
            body = resp.json()
            print(f"Received response from LitmusChaos API: {body}")
            if "errors" in body:
                raise RuntimeError(body["errors"])
            return body["data"]
        except httpx.RequestError as e:
            print(f"Request error when connecting to LitmusChaos API: {e}")
            raise RuntimeError(f"Request failed: {e}")
        except httpx.HTTPStatusError as e:
            print(f"HTTP error response from LitmusChaos API: {e.response.text}")
            raise RuntimeError(f"HTTP error: {e}")
        except Exception as e:
            print(f"Unexpected error when communicating with LitmusChaos API: {e}")
            raise RuntimeError(f"Unexpected error: {e}")

    # ── public operations ─────────────────────────────────────────────────

    def list_experiments(self) -> dict[str, Any]:
        """Return all experiments in the project."""
        query = """
        query ListExperiment($projectID: ID!, $request: ListExperimentRequest!) {
            listExperiment(projectID: $projectID, request: $request) {
                totalNoOfExperiments
                experiments {
                    experimentID
                    experimentType
                    experimentManifest
                    name
                    cronSyntax
                    isCustomExperiment
                    updatedAt
                    createdAt
                    isRemoved
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
            }
        }
        """
        variables = {
            "projectID": self._project_id,
            "request": {
                "experimentIDs": [],
                "pagination": {"page": 0, "limit": 50},
            },
             "sort": {
                "field": "NAME",
                "ascending": True
            },
            "filter": {}
        }
        return self._post({"query": query, "variables": variables})

    def list_environments(self) -> dict[str, Any]:
        """Return all environments in the project."""
        query = """
        query ListEnvironments($projectID: ID!, $request: ListEnvironmentRequest) {
            listEnvironments(projectID: $projectID, request: $request) {
                totalNoOfEnvironments
                environments {
                    environmentID
                    name
                    type
                    description
                    createdAt
                    updatedAt
                    infraIDs
                }
            }
        }
        """
        variables = {
            "projectID": self._project_id,
            "request": {
                "pagination": {"page": 0, "limit": 50},
            },
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

    def get_experiment_run(self, experiment_run_id: str) -> dict[str, Any]:
        """Fetch details of a specific experiment run."""
        query = """
        query GetExperimentRun(
            $projectID: ID!
            $experimentRunID: ID!
        ) {
            getExperimentRun(
                projectID: $projectID
                experimentRunID: $experimentRunID
            ) {
                experimentRunID
                experimentID
                experimentName
                phase
                resiliencyScore
                updatedAt
                infra {
                    name
                }
            }
        }
        """
        variables = {
            "projectID": self._project_id,
            "experimentRunID": experiment_run_id,
        }
        return self._post({"query": query, "variables": variables})

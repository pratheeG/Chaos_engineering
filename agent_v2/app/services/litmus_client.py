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
        query GetExperiment($projectID: ID!, $experimentID: ID!) {
            getExperiment(projectID: $projectID, experimentID: $experimentID) {
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
                

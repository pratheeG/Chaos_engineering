"""Prometheus client for querying historical metrics."""

from __future__ import annotations

import httpx
from datetime import datetime
from typing import Any


class PrometheusClient:
    """Thin synchronous wrapper around the Prometheus HTTP API."""

    def __init__(self, prometheus_url: str) -> None:
        self._url = prometheus_url.rstrip("/")

    def query(self, query: str, time: datetime | None = None) -> dict[str, Any]:
        """Run an instant query."""
        params = {"query": query}
        if time:
            params["time"] = time.isoformat()

        try:
            resp = httpx.get(
                f"{self._url}/api/v1/query",
                params=params,
                timeout=10.0,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            raise RuntimeError(f"Prometheus query failed: {e}")

    def query_range(
        self,
        query: str,
        start: datetime,
        end: datetime,
        step: str = "15s",
    ) -> dict[str, Any]:
        """Run a range query."""
        params = {
            "query": query,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "step": step,
        }

        try:
            resp = httpx.get(
                f"{self._url}/api/v1/query_range",
                params=params,
                timeout=10.0,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            raise RuntimeError(f"Prometheus range query failed: {e}")

    def get_container_metrics(
        self,
        namespace: str,
        pod_prefix: str,
        start: datetime,
        end: datetime,
    ) -> dict[str, Any]:
        """Fetch common container metrics for a pod prefix."""
        
        # 1. CPU Usage (rate over 1m)
        cpu_query = f'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}", pod=~"{pod_prefix}.*"}}[1m]))'
        
        # 2. Memory Usage
        mem_query = f'sum(container_memory_usage_bytes{{namespace="{namespace}", pod=~"{pod_prefix}.*"}})'

        # 3. Running Pod Count
        pod_query = f'count(kube_pod_status_phase{{namespace="{namespace}", pod=~"{pod_prefix}.*", phase="Running"}})'

        cpu_data = self.query_range(cpu_query, start, end)
        mem_data = self.query_range(mem_query, start, end)
        pod_data = self.query_range(pod_query, start, end)

        return {
            "cpu": cpu_data.get("data", {}).get("result", []),
            "memory": mem_data.get("data", {}).get("result", []),
            "pod_count": pod_data.get("data", {}).get("result", []),
        }

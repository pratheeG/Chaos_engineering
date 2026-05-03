"""Master Orchestrator FastAPI application.

Provides a unified interface for Chaos Planning and Execution.
"""

from __future__ import annotations

import sys
import os

# Add the app directory to the path so all internal packages resolve correctly.
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI

from graph.master import build_master_graph
from api.routes import router, set_graph

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Chaos Master Orchestrator",
    description="Unified LangGraph agent for Chaos Engineering (Planning + Execution).",
    version="3.0.0",
)

# Build the graph once and share it with the router
_master = build_master_graph()
set_graph(_master)

app.include_router(router)

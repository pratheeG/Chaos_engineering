"""Planner Agent FastAPI application.

Endpoints:
  POST /chat      – Send a message or resume after human-feedback pause.
  GET  /state/{thread_id} – Inspect the current graph state for a thread.
  DELETE /state/{thread_id} – Clear / reset a conversation thread.
"""

from __future__ import annotations

import sys
import os

# Add the app directory to the path so absolute-style imports work
# (same convention as agent/app/main.py running with `python main.py` or uvicorn from app/)
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

from graph import build_graph
from config import settings

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Chaos Planner Agent",
    description="LangGraph-powered Planner Agent for designing LitmusChaos experiments.",
    version="2.0.0",
)

# Single compiled graph instance with MemorySaver checkpointing
_planner = build_graph()


# ── Schemas ───────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    thread_id: str
    message: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _last_ai_message(state_values: dict) -> str:
    """Extract the latest non-tool-call AI message text."""
    from langchain_core.messages import AIMessage
    for msg in reversed(state_values.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", None):
            return msg.content
    return ""


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/chat")
async def chat(request: ChatRequest):
    """Send a user message. Handles both new conversations and resumed paused ones."""
    config = _config(request.thread_id)

    try:
        current = _planner.get_state(config)
        paused = len(current.next) > 0  # graph is frozen waiting for human_feedback

        if paused:
            # Append the user's feedback and resume
            _planner.update_state(config, {"messages": [HumanMessage(content=request.message)]})
            gen = _planner.stream(None, config, stream_mode="values")
        else:
            # Brand-new turn
            inputs = {"messages": [HumanMessage(content=request.message)], "confirmed": False}
            gen = _planner.stream(inputs, config, stream_mode="values")

        last_values = None
        for state_values in gen:
            last_values = state_values

        latest = _planner.get_state(config)
        waiting = len(latest.next) > 0

        return {
            "thread_id": request.thread_id,
            "status": "waiting_for_user" if waiting else "completed",
            "pending_nodes": list(latest.next),
            "message": _last_ai_message(last_values or {}),
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/state/{thread_id}")
async def get_state(thread_id: str):
    """Inspect the current state of a planning thread."""
    config = _config(thread_id)
    state = _planner.get_state(config)

    if not state.values:
        return {"thread_id": thread_id, "status": "not_found", "state": None}

    return {
        "thread_id": thread_id,
        "status": "waiting_for_user" if len(state.next) > 0 else "completed",
        "pending_nodes": list(state.next),
        "message_count": len(state.values.get("messages", [])),
        "confirmed": state.values.get("confirmed", False),
    }


@app.delete("/state/{thread_id}")
async def reset_state(thread_id: str):
    """Reset / clear a conversation thread."""
    # MemorySaver doesn't have an explicit delete; we overwrite with empty state.
    config = _config(thread_id)
    try:
        _planner.update_state(config, {"messages": [], "confirmed": False})
    except Exception:
        pass  # Thread may not exist yet
    return {"thread_id": thread_id, "status": "reset"}


@app.get("/health")
async def health():
    return {"status": "ok", "llm_provider": settings.llm_provider}

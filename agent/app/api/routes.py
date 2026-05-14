"""FastAPI route handlers for the Chaos Master Orchestrator."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage

from api.schemas import ChatRequest
from api.helpers import config, last_ai_message
from config import settings

router = APIRouter()

# Lazily resolved to avoid a circular import at module load time.
# The graph is created once in main.py and injected here.
_master = None


def set_graph(graph) -> None:
    """Inject the compiled LangGraph instance into this router."""
    global _master
    _master = graph


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/chat")
async def chat(request: ChatRequest):
    """Unified endpoint for the entire Chaos Lifecycle."""
    cfg = config(request.thread_id)

    try:
        current = _master.get_state(cfg)
        paused = len(current.next) > 0

        if paused:
            # Resume from human_feedback interrupt
            _master.update_state(cfg, {"messages": [HumanMessage(content=request.message)]})
            gen = _master.stream(None, cfg, stream_mode="values")
        else:
            # Brand-new turn
            inputs = {"messages": [HumanMessage(content=request.message)]}
            gen = _master.stream(inputs, cfg, stream_mode="values")

        last_values = None
        for state_values in gen:
            last_values = state_values

        latest = _master.get_state(cfg)
        waiting = len(latest.next) > 0

        state_to_check = last_values or latest.values or {}
        active_nodes = list(latest.next)

        # If the graph is waiting for human feedback, the next agent is always the supervisor
        if "human_feedback" in active_nodes:
            current_agent = "supervisor"
        else:
            current_agent = state_to_check.get("next_agent", "supervisor")

        return {
            "thread_id": request.thread_id,
            "status": "waiting_for_user" if waiting else "completed",
            "message": last_ai_message(state_to_check),
            "active_agent": current_agent,
            "pending_nodes": active_nodes,
        }

    except Exception as exc:
        print("=================================")
        print("Error in Chaos Orchestrator:", exc)
        print("=================================")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/state/{thread_id}")
async def get_state(thread_id: str):
    """Inspect the current state of a thread."""
    cfg = config(thread_id)
    state = _master.get_state(cfg)

    if not state.values:
        return {"thread_id": thread_id, "status": "not_found", "state": None}

    active_nodes = list(state.next)
    if "human_feedback" in active_nodes:
        active_agent = "supervisor"
    else:
        active_agent = state.values.get("next_agent", "supervisor")

    return {
        "thread_id": thread_id,
        "status": "waiting_for_user" if len(active_nodes) > 0 else "completed",
        "pending_nodes": active_nodes,
        "active_agent": active_agent,
        "message_count": len(state.values.get("messages", [])),
    }


@router.delete("/state/{thread_id}")
async def reset_state(thread_id: str):
    """Reset / clear a conversation thread."""
    cfg = config(thread_id)
    try:
        _master.update_state(cfg, {"messages": [], "confirmed": False, "completed": False})
    except Exception:
        pass
    return {"thread_id": thread_id, "status": "reset"}


@router.get("/health")
async def health():
    return {"status": "ok", "llm_provider": settings.llm_provider, "orchestrator": "v3-master"}


@router.get("/observer/verify/{experiment_id}")
async def verify_experiment(experiment_id: str):
    """Direct endpoint to trigger the Observer Agent's verification logic."""
    from tools.observer_tools import verify_experiment_run
    import json
    try:
        # verify_experiment_run returns a JSON string (ObservationReport)
        result_str = verify_experiment_run.invoke({"experiment_id": experiment_id})
        try:
            return json.loads(result_str)
        except json.JSONDecodeError:
            return {"detail": result_str}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

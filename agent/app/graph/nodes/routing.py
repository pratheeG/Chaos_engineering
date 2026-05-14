"""Routing (conditional edge) functions for the Master Orchestrator graph."""

from __future__ import annotations

from langgraph.graph import END

from graph.state import ChaosState


def route_from_supervisor(state: ChaosState) -> str:
    return state["next_agent"]


def route_from_planner(state: ChaosState) -> str:
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "planner_tools"

    # Once the planner finishes (no tool calls), always pause for human feedback.
    # The supervisor will decide whether the user's reply is an approval to execute.
    return "human_feedback"


def route_from_executor(state: ChaosState) -> str:
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "executor_tools"
    return END


def route_from_observer(state: ChaosState) -> str:
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "observer_tools"
    # Pause for human feedback (the supervisor will then decide if we go to feedback agent)
    return "human_feedback"


def route_from_feedback(state: ChaosState) -> str:
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "feedback_tools"
    return "human_feedback"

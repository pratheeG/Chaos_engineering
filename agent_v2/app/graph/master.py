"""Master Orchestrator graph builder.

Assembles the supervisor, planner, executor, and human-feedback nodes
into a single compiled LangGraph state machine.
"""

from __future__ import annotations

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from graph.state import ChaosState
from graph.nodes.supervisor import supervisor_node
from graph.nodes.planner import planner_node
from graph.nodes.executor import executor_node
from graph.nodes.observer import observer_node
from graph.nodes.human_feedback import human_feedback_node
from graph.nodes.routing import (
    route_from_supervisor, 
    route_from_planner, 
    route_from_executor,
    route_from_observer,
)
from tools.litmus import planner_tools, executor_tools
from tools.config_tool import config_tools
from tools.observer_tools import observer_tools
from tools.k8s_tools import observer_tools as k8s_observer_tools


# ── Graph Construction ────────────────────────────────────────────────────────

def build_master_graph():
    builder = StateGraph(ChaosState)

    builder.add_node("supervisor", supervisor_node)
    builder.add_node("planner", planner_node)
    builder.add_node("planner_tools", ToolNode(planner_tools))
    builder.add_node("executor", executor_node)
    builder.add_node("executor_tools", ToolNode(executor_tools + config_tools))
    builder.add_node("observer", observer_node)
    builder.add_node("observer_tools", ToolNode(observer_tools + k8s_observer_tools))
    builder.add_node("human_feedback", human_feedback_node)

    builder.set_entry_point("supervisor")

    # Supervisor → Planner / Executor / Observer / human_feedback (refusal)
    builder.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "planner": "planner", 
            "executor": "executor", 
            "observer": "observer",
            "human_feedback": "human_feedback"
        },
    )

    # Planner loop
    builder.add_conditional_edges(
        "planner",
        route_from_planner,
        {"planner_tools": "planner_tools", "human_feedback": "human_feedback"},
    )
    builder.add_edge("planner_tools", "planner")

    # Executor loop -> Pause for user confirmation before observation
    builder.add_conditional_edges(
        "executor",
        route_from_executor,
        {"executor_tools": "executor_tools", END: "human_feedback"},
    )
    builder.add_edge("executor_tools", "executor")

    # Observer loop -> Pause for follow-up user queries
    builder.add_conditional_edges(
        "observer",
        route_from_observer,
        {"observer_tools": "observer_tools", END: "human_feedback"},
    )
    builder.add_edge("observer_tools", "observer")

    # Resume from human feedback → supervisor re-evaluates intent
    builder.add_edge("human_feedback", "supervisor")

    memory = MemorySaver()
    return builder.compile(
        checkpointer=memory,
        interrupt_before=["human_feedback"],
    )

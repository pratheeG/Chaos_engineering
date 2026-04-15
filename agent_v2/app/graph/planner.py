"""Planner Agent LangGraph – wired to LitmusChaos + Kubernetes tools.

Flow:
  planner (LLM with tools) → tools (ToolNode) → planner → ...
                                                          ↘ interrupt_before=[human_feedback]
  human_feedback (no-op, waits for user resume) → planner → ... → END

The graph uses interrupt_before="human_feedback" so that after the planner
presents the summary, execution pauses and waits for the user's follow-up
message before continuing. This implements the Human-in-the-Loop pattern.
"""

from __future__ import annotations

from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from config import settings
from graph.state import PlannerState
from prompts.system import PLANNER_SYSTEM_PROMPT
from tools.litmus import planner_tools


# ── LLM factory (same pattern as agent/app/graph/agent.py) ───────────────────

def _get_llm():
    """Return an LLM instance based on config."""
    provider = settings.llm_provider.lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0,
        )
    elif provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=settings.groq_model,
            api_key=settings.groq_api_key,
            temperature=0,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}. Use 'openai' or 'groq'.")


# ── Node functions ────────────────────────────────────────────────────────────

def _call_planner(state: PlannerState) -> dict:
    """Node: invoke the LLM with tool bindings."""
    messages = state["messages"]

    # Inject system prompt at the front if not already present
    if not messages or messages[0].type != "system":
        messages = [SystemMessage(content=PLANNER_SYSTEM_PROMPT)] + messages
    print("messages ", messages)
    response = _llm_with_tools.invoke(messages)
    return {"messages": [response]}


def _human_feedback(state: PlannerState) -> dict:
    """No-op node – execution is interrupted HERE to wait for user input.
    Once the user provides input via /chat, the graph resumes from this node.
    """
    return {}


# ── Routing ───────────────────────────────────────────────────────────────────

def _should_continue(state: PlannerState) -> str:
    """After planner responds: route to tools, human_feedback pause, or END."""
    last = state["messages"][-1]

    # If the LLM made tool calls → execute tools
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"

    # Check if this response is the final confirmed handoff
    content = last.content.lower() if isinstance(last.content, str) else ""
    handoff_signals = ["passing to executor", "handing off", "executor agent", "approved"]
    if any(signal in content for signal in handoff_signals):
        return END

    # Otherwise pause for human input (summary presented, waiting for approve/feedback)
    return "human_feedback"


def _after_feedback(state: PlannerState) -> str:
    """After user provides feedback, always route back to the planner."""
    return "planner"


# ── Graph construction ────────────────────────────────────────────────────────

# Module-level LLM (initialised once at import)
_llm = _get_llm()
_llm_with_tools = _llm.bind_tools(planner_tools)


def build_graph():
    """Construct and compile the Planner LangGraph with memory checkpointing."""
    graph = StateGraph(PlannerState)

    # Nodes
    graph.add_node("planner", _call_planner)
    graph.add_node("tools", ToolNode(planner_tools))
    graph.add_node("human_feedback", _human_feedback)

    # Entry
    graph.set_entry_point("planner")

    # Edges
    graph.add_conditional_edges(
        "planner",
        _should_continue,
        {"tools": "tools", "human_feedback": "human_feedback", END: END},
    )
    graph.add_edge("tools", "planner")
    graph.add_conditional_edges(
        "human_feedback",
        _after_feedback,
        {"planner": "planner"},
    )

    memory = MemorySaver()
    # Interrupt BEFORE human_feedback so the graph freezes after the planner summary
    return graph.compile(checkpointer=memory, interrupt_before=["human_feedback"])

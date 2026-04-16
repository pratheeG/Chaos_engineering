"""Executor Agent LangGraph – wired to LitmusChaos + Config tools.

Flow:
  executor (LLM with tools) → tools (ToolNode) → executor → ...
                                                             ↘ END
"""

from __future__ import annotations

from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from config import settings
from graph.state import ExecutorState
from prompts.executor_prompt import EXECUTOR_SYSTEM_PROMPT
from tools.litmus import executor_tools
from tools.config_tool import config_tools


# Combine tools
all_executor_tools = executor_tools + config_tools

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


def _call_executor(state: ExecutorState) -> dict:
    """Node: invoke the LLM with tool bindings."""
    messages = state["messages"]

    # Inject system prompt at the front if not already present
    if not messages or messages[0].type != "system":
        messages = [SystemMessage(content=EXECUTOR_SYSTEM_PROMPT)] + messages
    
    response = _llm_with_tools.invoke(messages)
    return {"messages": [response]}


def _should_continue(state: ExecutorState) -> str:
    """After executor responds: route to tools or END."""
    last = state["messages"][-1]

    # If the LLM made tool calls → execute tools
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"

    # Otherwise execution has finished
    return END


# ── Graph construction ────────────────────────────────────────────────────────

_llm = _get_llm()
_llm_with_tools = _llm.bind_tools(all_executor_tools)


def build_executor_graph():
    """Construct and compile the Executor LangGraph with memory checkpointing."""
    graph = StateGraph(ExecutorState)

    # Nodes
    graph.add_node("executor", _call_executor)
    graph.add_node("tools", ToolNode(all_executor_tools))

    # Entry
    graph.set_entry_point("executor")

    # Edges
    graph.add_conditional_edges(
        "executor",
        _should_continue,
        {"tools": "tools", END: END},
    )
    graph.add_edge("tools", "executor")

    memory = MemorySaver()
    return graph.compile(checkpointer=memory)

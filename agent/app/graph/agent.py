"""LangGraph ReAct agent wired to LitmusChaos tools."""

from __future__ import annotations

from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from config import settings
from graph.state import AgentState
from prompts.system import SYSTEM_PROMPT
from tools.litmus import litmus_tools


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


def _should_continue(state: AgentState) -> str:
    """Edge function: decide whether to call tools or finish."""
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END


def _call_model(state: AgentState) -> AgentState:
    """Node: invoke the LLM with the current message history."""
    messages = state["messages"]

    # Inject system prompt if not already present
    if not messages or messages[0].type != "system":
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

    response = _llm_with_tools.invoke(messages)
    return {"messages": [response]}


# Module-level LLM (initialised once)
_llm = _get_llm()
_llm_with_tools = _llm.bind_tools(litmus_tools)


def build_graph():
    """Construct and compile the LangGraph agent."""
    graph = StateGraph(AgentState)

    # Nodes
    graph.add_node("agent", _call_model)
    graph.add_node("tools", ToolNode(litmus_tools))

    # Edges
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", _should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()

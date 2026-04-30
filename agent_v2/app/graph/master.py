"""Master Orchestrator (Supervisor) Graph.

Unifies Planner and Executor into a single state machine.
The Supervisor analyzes user intent and routes to the appropriate agent.
"""

from __future__ import annotations

import operator
from typing import Annotated, Sequence, TypedDict, Literal

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from config import settings
from graph.state import ChaosState
from prompts.chaos_prompts import (
    PLANNER_SYSTEM_PROMPT,
    EXECUTOR_SYSTEM_PROMPT,
    SUPERVISOR_SYSTEM_PROMPT,
)
from tools.litmus import planner_tools, executor_tools
from tools.config_tool import config_tools

# ── LLM Factory ───────────────────────────────────────────────────────────────

def _get_llm(temperature=0):
    provider = settings.llm_provider.lower()
    if provider == "openai":
        return ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key, temperature=temperature)
    elif provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(model=settings.groq_model, api_key=settings.groq_api_key, temperature=temperature)
    elif provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=settings.ollama_model, base_url=settings.ollama_base_url, temperature=temperature)
    raise ValueError(f"Unsupported provider: {provider}")

# ── Nodes ─────────────────────────────────────────────────────────────────────

def supervisor_node(state: ChaosState) -> dict:
    """Master router: Decides which agent should handle the next turn."""
    messages = state["messages"]
    
    # Simple logic-based routing to save tokens, or use an LLM
    # For now, let's use an LLM to be robust to natural language
    llm = _get_llm()
    
    # Filter out ALL tool-related messages and only keep user/assistant text
    clean_messages = []
    # Only look at the last 10 messages for context, but strictly filter
    for msg in messages[-10:]:
        # Skip tool messages and AI messages that have tool calls
        if msg.type == "tool" or (hasattr(msg, "tool_calls") and msg.tool_calls):
            continue
        
        # Also clean content to remove any tool-like JSON blocks that might confuse the model
        content = msg.content
        if isinstance(content, str) and '"arguments":' in content and '"name":' in content:
            continue
            
        clean_messages.append(msg)
    
    # Ensure we don't have an empty list, but keep it minimal
    clean_messages = clean_messages[-5:]
            
    # Get supported faults from registry
    import json
    try:
        with open("app/fault_registry.json", "r") as f:
            registry = json.load(f)
            fault_list = ", ".join(registry.keys())
    except:
        fault_list = "pod-delete, pod-cpu-hog, pod-memory-hog"
            
    system_msg_content = SUPERVISOR_SYSTEM_PROMPT.format(supported_faults=fault_list)
    system_msg = SystemMessage(content=system_msg_content + "\nRespond with 'planner', 'executor', or the polite refusal message.")
    
    response = llm.invoke([system_msg] + clean_messages)
    
    decision = response.content.lower().strip().replace("'", "").replace('"', "")
    
    if "executor" == decision:
        return {"next_agent": "executor"}
    elif "planner" == decision:
        return {"next_agent": "planner"}
    else:
        # It's a refusal message or something else
        # Append the refusal message to the conversation and go to human_feedback
        from langchain_core.messages import AIMessage
        return {
            "messages": [AIMessage(content=response.content)],
            "next_agent": "human_feedback"
        }

def planner_node(state: ChaosState) -> dict:
    """Planner Agent: Designs the experiment."""
    messages = state["messages"]
    llm = _get_llm().bind_tools(planner_tools)
    
    if not messages or messages[0].type != "system":
        messages = [SystemMessage(content=PLANNER_SYSTEM_PROMPT)] + messages
    else:
        # Ensure correct system prompt is at the front
        messages[0] = SystemMessage(content=PLANNER_SYSTEM_PROMPT)
        
    response = llm.invoke(messages)
    return {"messages": [response]}

def executor_node(state: ChaosState) -> dict:
    """Executor Agent: Implements and runs the experiment."""
    messages = state["messages"]
    all_exec_tools = executor_tools + config_tools
    llm = _get_llm().bind_tools(all_exec_tools)
    
    # Replace planner system prompt with executor system prompt
    if messages and messages[0].type == "system":
        messages = [SystemMessage(content=EXECUTOR_SYSTEM_PROMPT)] + messages[1:]
    else:
        messages = [SystemMessage(content=EXECUTOR_SYSTEM_PROMPT)] + messages
        
    response = llm.invoke(messages)
    return {"messages": [response]}

def human_feedback_node(state: ChaosState) -> dict:
    """Pause point for human feedback. 
    The graph interrupts BEFORE this node. When resumed, it flows to the supervisor.
    """
    return {"next_agent": "supervisor"} # Reset to supervisor for the next turn

# ── Routing ───────────────────────────────────────────────────────────────────

def route_from_supervisor(state: ChaosState) -> str:
    return state["next_agent"]

def route_from_planner(state: ChaosState) -> str:
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "planner_tools"
    
    # Once the planner is done (no tool calls), always pause for human feedback.
    # The supervisor will then decide if the user's response is an approval to execute.
    return "human_feedback"

def route_from_executor(state: ChaosState) -> str:
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "executor_tools"
    return END

# ── Graph Construction ────────────────────────────────────────────────────────

def build_master_graph():
    builder = StateGraph(ChaosState)
    
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("planner", planner_node)
    builder.add_node("planner_tools", ToolNode(planner_tools))
    builder.add_node("executor", executor_node)
    builder.add_node("executor_tools", ToolNode(executor_tools + config_tools))
    builder.add_node("human_feedback", human_feedback_node)
    
    builder.set_entry_point("supervisor")
    
    # Supervisor -> Planner/Executor
    builder.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {"planner": "planner", "executor": "executor", "human_feedback": "human_feedback"}
    )
    
    # Planner Loop
    builder.add_conditional_edges(
        "planner",
        route_from_planner,
        {"planner_tools": "planner_tools", "human_feedback": "human_feedback"}
    )
    builder.add_edge("planner_tools", "planner")
    
    # Executor Loop
    builder.add_conditional_edges(
        "executor",
        route_from_executor,
        {"executor_tools": "executor_tools", END: END}
    )
    builder.add_edge("executor_tools", "executor")
    
    # Resume from feedback always goes to supervisor to re-evaluate intent
    builder.add_edge("human_feedback", "supervisor")
    
    memory = MemorySaver()
    return builder.compile(
        checkpointer=memory,
        interrupt_before=["human_feedback"]
    )

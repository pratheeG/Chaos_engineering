"""Supervisor node — routes user intent to the correct agent."""

from __future__ import annotations

import json

from langchain_core.messages import AIMessage, SystemMessage

from graph.llm import get_llm
from graph.state import ChaosState
from prompts.chaos_prompts import SUPERVISOR_SYSTEM_PROMPT


def supervisor_node(state: ChaosState) -> dict:
    """Master router: Decides which agent should handle the next turn."""
    messages = state["messages"]

    llm = get_llm()

    # Filter out ALL tool-related messages; only keep plain user/assistant text
    clean_messages = []
    for msg in messages[-10:]:
        if msg.type == "tool" or (hasattr(msg, "tool_calls") and msg.tool_calls):
            continue
        content = msg.content
        if isinstance(content, str) and '"arguments":' in content and '"name":' in content:
            continue
        clean_messages.append(msg)

    # Keep it minimal
    clean_messages = clean_messages[-5:]

    # Get supported faults from registry
    try:
        with open("app/fault_registry.json", "r") as f:
            registry = json.load(f)
            fault_list = ", ".join(registry.keys())
    except Exception:
        fault_list = "pod-delete, pod-cpu-hog, pod-memory-hog"

    system_msg = SystemMessage(
        content=SUPERVISOR_SYSTEM_PROMPT.format(supported_faults=fault_list)
        + "\nRespond with 'planner', 'executor', 'observer', 'feedback', or the polite refusal message."
    )

    response = llm.invoke([system_msg] + clean_messages)
    decision = response.content.lower().strip().replace("'", "").replace('"', "")

    if decision == "executor":
        return {"next_agent": "executor"}
    elif decision == "planner":
        return {"next_agent": "planner"}
    elif decision == "observer":
        return {"next_agent": "observer"}
    elif decision == "feedback":
        return {"next_agent": "feedback"}
    else:
        # Refusal or unrecognised — surface the message and pause for human input
        return {
            "messages": [AIMessage(content=response.content)],
            "next_agent": "human_feedback",
        }

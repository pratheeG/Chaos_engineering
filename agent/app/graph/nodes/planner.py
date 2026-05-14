"""Planner node — designs the chaos experiment."""

from __future__ import annotations

from langchain_core.messages import SystemMessage

from graph.llm import get_llm
from graph.state import ChaosState
from prompts.chaos_prompts import PLANNER_SYSTEM_PROMPT
from tools.litmus import planner_tools


def planner_node(state: ChaosState) -> dict:
    """Planner Agent: Designs the experiment."""
    messages = state["messages"]

    llm = get_llm().bind_tools(planner_tools)

    if not messages or messages[0].type != "system":
        messages = [SystemMessage(content=PLANNER_SYSTEM_PROMPT)] + messages
    else:
        # Ensure the correct system prompt is at the front
        messages[0] = SystemMessage(content=PLANNER_SYSTEM_PROMPT)

    response = llm.invoke(messages)
    return {"messages": [response]}

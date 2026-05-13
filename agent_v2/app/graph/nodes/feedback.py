"""Feedback node — analyzes results and suggests improvements."""

from __future__ import annotations

from langchain_core.messages import SystemMessage

from graph.llm import get_llm
from graph.state import ChaosState
from prompts.chaos_prompts import FEEDBACK_SYSTEM_PROMPT
from tools.observer_tools import observer_tools
from tools.litmus import planner_tools

# Feedback Agent has access to both observation and planning tools 
# to suggest and schema-check improvements.
_feedback_tools = observer_tools + planner_tools


def feedback_node(state: ChaosState) -> dict:
    """Feedback Agent: Provides suggestions for experiment improvement."""
    messages = state["messages"]

    llm = get_llm().bind_tools(_feedback_tools)

    # Inject system prompt
    if messages and messages[0].type == "system":
        messages = [SystemMessage(content=FEEDBACK_SYSTEM_PROMPT)] + messages[1:]
    else:
        messages = [SystemMessage(content=FEEDBACK_SYSTEM_PROMPT)] + messages

    response = llm.invoke(messages)
    return {"messages": [response]}

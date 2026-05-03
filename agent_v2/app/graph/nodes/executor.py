"""Executor node — implements and runs the chaos experiment."""

from __future__ import annotations

from langchain_core.messages import SystemMessage

from graph.llm import get_llm
from graph.state import ChaosState
from prompts.chaos_prompts import EXECUTOR_SYSTEM_PROMPT
from tools.litmus import executor_tools
from tools.config_tool import config_tools


def executor_node(state: ChaosState) -> dict:
    """Executor Agent: Implements and runs the experiment."""
    messages = state["messages"]

    all_exec_tools = executor_tools + config_tools
    llm = get_llm().bind_tools(all_exec_tools)

    # Replace any existing system prompt with the executor's prompt
    if messages and messages[0].type == "system":
        messages = [SystemMessage(content=EXECUTOR_SYSTEM_PROMPT)] + messages[1:]
    else:
        messages = [SystemMessage(content=EXECUTOR_SYSTEM_PROMPT)] + messages

    response = llm.invoke(messages)
    return {"messages": [response]}

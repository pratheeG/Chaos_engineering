"""Observer node — verifies chaos experiment results against Kubernetes signals."""

from __future__ import annotations

from langchain_core.messages import SystemMessage

from graph.llm import get_llm
from graph.state import ChaosState
from prompts.chaos_prompts import OBSERVER_SYSTEM_PROMPT
from tools.observer_tools import observer_tools
from tools.k8s_tools import observer_tools as k8s_observer_tools  # list_pods, get_pod_events, get_pod_logs, get_pod_resource_usage

_all_observer_tools = observer_tools + k8s_observer_tools


def observer_node(state: ChaosState) -> dict:
    """Observer Agent: Verifies that chaos experiments ran as configured."""
    messages = state["messages"]

    llm = get_llm().bind_tools(_all_observer_tools)

    if messages and messages[0].type == "system":
        messages = [SystemMessage(content=OBSERVER_SYSTEM_PROMPT)] + messages[1:]
    else:
        messages = [SystemMessage(content=OBSERVER_SYSTEM_PROMPT)] + messages

    response = llm.invoke(messages)
    return {"messages": [response]}

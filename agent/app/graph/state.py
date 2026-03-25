"""Agent state definition for LangGraph."""

from __future__ import annotations

from typing import Annotated
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """State that flows through the LangGraph agent."""
    messages: Annotated[list[BaseMessage], add_messages]

"""Planner Agent state definition for LangGraph."""

from __future__ import annotations

from typing import Annotated
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class PlannerState(TypedDict):
    """State that flows through the Planner Agent LangGraph."""
    messages: Annotated[list[BaseMessage], add_messages]
    # Whether user has confirmed the final plan
    confirmed: bool

class ExecutorState(TypedDict):
    """State that flows through the Executor Agent LangGraph."""
    messages: Annotated[list[BaseMessage], add_messages]
    completed: bool

"""Unified state definition for the Master Orchestrator."""

from __future__ import annotations

from typing import Annotated, Literal
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class ChaosState(TypedDict):
    """Shared state for the entire Chaos Lifecycle (Plan -> Execute)."""
    messages: Annotated[list[BaseMessage], add_messages]
    
    # Routing control
    next_agent: Literal["planner", "executor", "end"]
    
    # State flags
    confirmed: bool
    completed: bool

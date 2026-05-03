"""Pydantic request/response schemas for the Chaos Master Orchestrator API."""

from __future__ import annotations

from pydantic import BaseModel


class ChatRequest(BaseModel):
    thread_id: str
    message: str

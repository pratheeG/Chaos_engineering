"""Centralised configuration loaded from environment / .env file."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import Field

# Load .env from agent root (one level above this file)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


class Settings(BaseSettings):
    # ── LLM ──────────────────────────────────────────────────────────────
    llm_provider: str = Field(default="groq", description="openai | groq")

    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-4o")

    groq_api_key: str = Field(default="")
    groq_model: str = Field(default="llama-3.3-70b-versatile")

    # ── LitmusChaos ──────────────────────────────────────────────────────
    litmus_api_url: str = Field(default="http://localhost:9002/api/query")
    litmus_project_id: str = Field(default="")
    litmus_access_token: str = Field(default="")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

"""Centralised configuration loaded from root .env file."""

from __future__ import annotations

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv

# Resolve root .env: agent_v2/app/config.py -> agent_v2/app -> agent_v2 -> project root
_root_env = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=_root_env, override=False)


class Settings(BaseSettings):
    # ── LLM ──────────────────────────────────────────────────────────────────
    llm_provider: str = Field(default="groq", description="openai | groq")

    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-4o")

    groq_api_key: str = Field(default="")
    groq_model: str = Field(default="llama-3.3-70b-versatile")

    # ── LitmusChaos ──────────────────────────────────────────────────────────
    chaos_center_endpoint: str = Field(default="http://localhost:9002")
    litmus_project_id: str = Field(default="")
    litmus_access_token: str = Field(default="")
    litmus_hub_id: str = Field(default="")

    @property
    def litmus_api_url(self) -> str:
        return f"{self.chaos_center_endpoint}/api/query"

    class Config:
        env_file_encoding = "utf-8"


settings = Settings()

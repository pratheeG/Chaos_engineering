"""Centralised configuration loaded from root .env file."""

from __future__ import annotations

import os
import json
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from dotenv import load_dotenv

# Resolve root .env: agent_v2/app/config.py -> agent_v2/app -> agent_v2 -> project root
_root_env = Path(__file__).resolve().parent.parent.parent / ".env"

# Load explicitly just in case Pydantic misses it for os.environ purposes
load_dotenv(dotenv_path=_root_env, override=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_root_env),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM ──────────────────────────────────────────────────────────────────
    llm_provider: str = Field(default="groq", description="openai | groq | ollama")

    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-4o")

    groq_api_key: str = Field(default="")
    groq_model: str = Field(default="llama-3.3-70b-versatile")

    ollama_model: str = Field(default="llama3")
    ollama_base_url: str = Field(default="http://localhost:11434")

    # ── LitmusChaos ──────────────────────────────────────────────────────────
    chaos_center_endpoint: str = Field(default="http://localhost:9002")
    litmus_project_id: str = Field(default="")
    litmus_access_token: str = Field(default="")
    litmus_hub_id: str = Field(default="")
    litmus_infra_id: str = Field(default="")

    # ── Prometheus ──────────────────────────────────────────────────────────
    prometheus_url: str = Field(default="http://localhost:9090")

    # ── LangSmith (Tracing) ──────────────────────────────────────────────────
    langsmith_tracing: str = Field(default="false", validation_alias="LANGSMITH_TRACING")
    langsmith_endpoint: str = Field(default="https://api.smith.langchain.com", validation_alias="LANGSMITH_ENDPOINT")
    langsmith_api_key: str = Field(default="", validation_alias="LANGSMITH_API_KEY")
    langsmith_project: str = Field(default="chaos-engineering", validation_alias="LANGSMITH_PROJECT")

    @property
    def litmus_api_url(self) -> str:
        return f"{self.chaos_center_endpoint}/api/query"


try:
    settings = Settings()
    
    # ── Export LangSmith variables to environment ────────────────────────────────
    # LangChain and LangGraph automatically pick these up from os.environ
    if settings.langsmith_tracing.lower() == "true":
        print(f"DEBUG: LangSmith tracing enabled for project: {settings.langsmith_project}")
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    else:
        print("DEBUG: LangSmith tracing is DISABLED (check .env file)")

except Exception as e:
    print(f"CRITICAL: Failed to load settings: {e}")
    # Fallback to empty settings if needed or re-raise
    raise
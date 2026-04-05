"""Centralised configuration loaded from environment / Secrets.toml file."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from pydantic_settings import BaseSettings
from pydantic import Field

# Load Secrets.toml from agent root (one level above this file)
_env_path = Path(__file__).resolve().parent.parent / "Secrets.toml"
try:
    with open(_env_path, "rb") as f:
        data = tomllib.load(f)
    for key, value in data.items():
        os.environ[key] = str(value)
except FileNotFoundError:
    print(f"Secrets.toml not found at {_env_path}, using environment variables only")


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
        env_file_encoding = "utf-8"


settings = Settings()

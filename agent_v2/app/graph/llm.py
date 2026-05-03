"""LLM factory for the Master Orchestrator."""

from __future__ import annotations

from config import settings


def get_llm(temperature: int = 0):
    """Return the configured LLM instance based on ``settings.llm_provider``."""
    provider = settings.llm_provider.lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=temperature,
        )
    elif provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=settings.groq_model,
            api_key=settings.groq_api_key,
            temperature=temperature,
        )
    elif provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=temperature,
        )

    raise ValueError(f"Unsupported LLM provider: {provider!r}")

"""
config/llm_factory.py
──────────────────────────────────────────────────────────────
LLM Factory — builds the correct LLM client based on
LLM_PROVIDER in .env.

Why a factory?
  Both agents (collector + analyst) need an LLM.
  Centralizing construction here means:
    • Switching providers = change ONE env var, zero code
    • Temperature is set per-call, not baked in
    • Easy to add new providers (Anthropic, Mistral, etc.)

Usage:
    from config.llm_factory import build_llm
    llm = build_llm(temperature=0)       # for Collector
    llm = build_llm(temperature=0.2)     # for Analyst
──────────────────────────────────────────────────────────────
"""

from config.settings import settings
from config.logger import logger


def build_llm(temperature: float = 0):
    """
    Returns a LangChain chat model for the configured provider.

    Args:
        temperature: 0 = deterministic, 0.2 = slightly creative

    Returns:
        ChatGroq | ChatOpenAI instance (both share the same
        LangChain BaseChatModel interface — agents don't care which)

    Raises:
        ValueError: if provider is unknown or key is missing
    """
    provider = settings.llm_provider

    if provider == "groq":
        if not settings.has_groq_key:
            raise ValueError(
                "GROQ_API_KEY not set or is a placeholder. "
                "Get a free key at console.groq.com"
            )
        from langchain_groq import ChatGroq
        logger.info(f"[llm_factory] Building Groq LLM — model={settings.groq_model}")
        return ChatGroq(
            model=settings.groq_model,
            temperature=temperature,
            api_key=settings.groq_api_key,
            max_tokens=2048,
        )

    elif provider == "openai":
        if not settings.has_openai_key:
            raise ValueError(
                "OPENAI_API_KEY not set or is a placeholder. "
                "Get a key at platform.openai.com"
            )
        from langchain_openai import ChatOpenAI
        logger.info(f"[llm_factory] Building OpenAI LLM — model={settings.openai_model}")
        return ChatOpenAI(
            model=settings.openai_model,
            temperature=temperature,
            api_key=settings.openai_api_key,
        )

    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER='{provider}'. "
            f"Valid options: 'groq', 'openai'"
        )
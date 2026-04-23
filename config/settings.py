"""
config/settings.py
──────────────────────────────────────────────────────────────
Centralized config — reads from:
  1. Streamlit secrets (st.secrets) — when deployed on cloud
  2. Environment variables / .env   — when running locally

Priority: Streamlit secrets > .env > defaults

This dual-source pattern means the same code works both
locally (via .env) and on Streamlit Cloud (via secrets UI)
without any changes.
──────────────────────────────────────────────────────────────
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")


def _get(key: str, default: str = "") -> str:
    """
    Reads a config value from Streamlit secrets first,
    then falls back to environment variables.
    """
    try:
        import streamlit as st
        # st.secrets raises an error if key not found
        val = st.secrets.get(key)
        if val is not None:
            return str(val)
    except Exception:
        pass
    return os.getenv(key, default)


class Settings:

    # ── Groq ──────────────────────────────────────────────────
    @property
    def groq_api_key(self) -> str:
        return _get("GROQ_API_KEY")

    @property
    def groq_model(self) -> str:
        return _get("GROQ_MODEL", "llama-3.3-70b-versatile")

    @property
    def has_groq_key(self) -> bool:
        k = self.groq_api_key
        return bool(k) and "your-groq" not in k and "your_key" not in k

    # ── OpenAI ────────────────────────────────────────────────
    @property
    def openai_api_key(self) -> str:
        return _get("OPENAI_API_KEY")

    @property
    def openai_model(self) -> str:
        return _get("OPENAI_MODEL", "gpt-4o-mini")

    @property
    def has_openai_key(self) -> bool:
        k = self.openai_api_key
        return bool(k) and not k.startswith("sk-your")

    # ── Active provider ───────────────────────────────────────
    @property
    def llm_provider(self) -> str:
        return _get("LLM_PROVIDER", "groq").lower()

    @property
    def active_model(self) -> str:
        return self.groq_model if self.llm_provider == "groq" else self.openai_model

    @property
    def has_llm_key(self) -> bool:
        if self.llm_provider == "groq":
            return self.has_groq_key
        return self.has_openai_key

    # ── News & Stock APIs ─────────────────────────────────────
    @property
    def news_api_key(self) -> str:
        return _get("NEWS_API_KEY")

    @property
    def has_news_api_key(self) -> bool:
        k = self.news_api_key
        return bool(k) and "your" not in k.lower()

    @property
    def alpha_vantage_api_key(self) -> str:
        return _get("ALPHA_VANTAGE_API_KEY")

    # ── App behaviour ─────────────────────────────────────────
    @property
    def use_mock_data(self) -> bool:
        return _get("USE_MOCK_DATA", "true").lower() == "true"

    @property
    def log_level(self) -> str:
        return _get("LOG_LEVEL", "INFO").upper()

    @property
    def max_retries(self) -> int:
        return int(_get("MAX_RETRIES", "3"))

    @property
    def request_timeout(self) -> int:
        return int(_get("REQUEST_TIMEOUT", "30"))

    def validate(self) -> list[str]:
        warnings = []
        if not self.has_llm_key:
            warnings.append(
                f"⚠️  No valid {self.llm_provider.upper()} key found"
            )
        if not self.has_news_api_key:
            warnings.append("⚠️  NEWS_API_KEY not set — using mock news")
        if not self.alpha_vantage_api_key:
            warnings.append("⚠️  ALPHA_VANTAGE_API_KEY not set — using mock stock")
        return warnings

    def __repr__(self) -> str:
        return (
            f"Settings(provider={self.llm_provider}, "
            f"model={self.active_model}, "
            f"mock={self.use_mock_data}, "
            f"llm_ready={self.has_llm_key})"
        )


settings = Settings()
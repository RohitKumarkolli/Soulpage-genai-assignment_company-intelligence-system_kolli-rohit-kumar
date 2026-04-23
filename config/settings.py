"""
config/settings.py
──────────────────────────────────────────────────────────────
Centralized configuration — now supports both OpenAI and Groq.

LLM_PROVIDER controls which backend is used:
  "groq"   → ChatGroq  (free, fast, llama-3.3-70b)
  "openai" → ChatOpenAI (paid, gpt-4o-mini)

Usage anywhere:
    from config.settings import settings
    print(settings.llm_provider)
──────────────────────────────────────────────────────────────
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")


class Settings:

    # ── OpenAI ────────────────────────────────────────────────
    @property
    def openai_api_key(self) -> str:
        return os.getenv("OPENAI_API_KEY", "")

    @property
    def openai_model(self) -> str:
        return os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    @property
    def has_openai_key(self) -> bool:
        k = self.openai_api_key
        return bool(k) and not k.startswith("sk-your")

    # ── Groq ──────────────────────────────────────────────────
    @property
    def groq_api_key(self) -> str:
        return os.getenv("GROQ_API_KEY", "")

    @property
    def groq_model(self) -> str:
        return os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    @property
    def has_groq_key(self) -> bool:
        k = self.groq_api_key
        return bool(k) and not k.startswith("your-groq")

    # ── Active LLM provider ───────────────────────────────────
    @property
    def llm_provider(self) -> str:
        """'groq' | 'openai' — set via LLM_PROVIDER in .env"""
        return os.getenv("LLM_PROVIDER", "groq").lower()

    @property
    def active_model(self) -> str:
        """The model name for whichever provider is active."""
        return self.groq_model if self.llm_provider == "groq" else self.openai_model

    @property
    def has_llm_key(self) -> bool:
        """True if the active provider has a valid key."""
        if self.llm_provider == "groq":
            return self.has_groq_key
        return self.has_openai_key

    # ── News & Stock APIs ─────────────────────────────────────
    @property
    def news_api_key(self) -> str:
        return os.getenv("NEWS_API_KEY", "")

    @property
    def has_news_api_key(self) -> bool:
        k = self.news_api_key
        return bool(k) and "your-" not in k

    @property
    def alpha_vantage_api_key(self) -> str:
        return os.getenv("ALPHA_VANTAGE_API_KEY", "")

    # ── LangSmith ─────────────────────────────────────────────
    @property
    def langchain_tracing(self) -> bool:
        return os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"

    @property
    def langchain_api_key(self) -> str:
        return os.getenv("LANGCHAIN_API_KEY", "")

    @property
    def langchain_project(self) -> str:
        return os.getenv("LANGCHAIN_PROJECT", "company-intelligence")

    # ── App behaviour ─────────────────────────────────────────
    @property
    def use_mock_data(self) -> bool:
        return os.getenv("USE_MOCK_DATA", "true").lower() == "true"

    @property
    def log_level(self) -> str:
        return os.getenv("LOG_LEVEL", "INFO").upper()

    @property
    def max_retries(self) -> int:
        return int(os.getenv("MAX_RETRIES", "3"))

    @property
    def request_timeout(self) -> int:
        return int(os.getenv("REQUEST_TIMEOUT", "30"))

    def validate(self) -> list[str]:
        warnings = []
        if not self.has_llm_key:
            warnings.append(
                f"⚠️  No valid {self.llm_provider.upper()} key — "
                f"LLM calls will fail (mock mode ok)"
            )
        if not self.has_news_api_key:
            warnings.append("⚠️  NEWS_API_KEY not set — using mock news data")
        if not self.alpha_vantage_api_key:
            warnings.append("⚠️  ALPHA_VANTAGE_API_KEY not set — using mock stock data")
        return warnings

    def __repr__(self) -> str:
        return (
            f"Settings(provider={self.llm_provider}, "
            f"model={self.active_model}, "
            f"mock={self.use_mock_data}, "
            f"llm_ready={self.has_llm_key})"
        )


settings = Settings()
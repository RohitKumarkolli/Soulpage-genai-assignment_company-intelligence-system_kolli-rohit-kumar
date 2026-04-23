"""
agents/data_collector.py
──────────────────────────────────────────────────────────────
Agent 1: Data Collector

Responsibilities:
  1. Receive company name from graph state
  2. Call both tools directly (news + stock)
  3. Validate and structure the collected data
  4. Write CollectorOutput into graph state

Design decision — why NO LLM in the Collector:
  The collector's job is 100% deterministic:
    "Always fetch news. Always fetch stock. Return both."
  There is no reasoning needed — no branching, no judgment.
  Using an LLM here added cost, latency, and provider-specific
  bugs (tool_choice varies across OpenAI / Groq / Anthropic).

  The LLM lives in the Analyst, where reasoning IS the job.
──────────────────────────────────────────────────────────────
"""

from datetime import datetime
from agents.state import CompanyIntelState, CollectorOutput
from tools import fetch_company_news, fetch_stock_data
from config.settings import settings
from config.logger import logger


def _run_direct(company: str) -> tuple[dict, dict, list[str]]:
    """
    Calls both tools directly and returns structured results.
    No LLM — fast, free, deterministic, provider-agnostic.
    """
    logger.info(f"[collector] Fetching data for '{company}'")
    errors = []

    # ── Fetch news ────────────────────────────────────────────
    if settings.use_mock_data or not settings.has_news_api_key:
        logger.info(f"[collector] News: using mock data")
    else:
        logger.info(f"[collector] News: calling live NewsAPI")

    news_result = fetch_company_news.invoke({"company": company})
    if not news_result.get("success"):
        errors.append(f"News fetch failed: {news_result.get('error', 'unknown')}")
        logger.warning(f"[collector] News tool failed: {news_result.get('error')}")

    # ── Fetch stock ───────────────────────────────────────────
    if settings.use_mock_data or not settings.alpha_vantage_api_key:
        logger.info(f"[collector] Stock: using mock data")
    else:
        logger.info(f"[collector] Stock: calling live Alpha Vantage")

    stock_result = fetch_stock_data.invoke({"company": company})
    if not stock_result.get("success"):
        errors.append(f"Stock fetch failed: {stock_result.get('error', 'unknown')}")
        logger.warning(f"[collector] Stock tool failed: {stock_result.get('error')}")

    return news_result, stock_result, errors


def data_collector_node(state: CompanyIntelState) -> dict:
    """
    LangGraph node for the Data Collector agent.

    Reads:  state["company"]
    Writes: state["raw_data"], state["collector_status"]

    Always calls both tools. Status reflects data quality:
      success → both tools returned data
      partial → one tool returned data
      failed  → both tools returned nothing
    """
    company = state["company"]
    logger.info(f"[collector] ▶ Starting data collection for '{company}'")

    try:
        news_result, stock_result, errors = _run_direct(company)

        news_ok  = news_result.get("success", False)
        stock_ok = stock_result.get("success", False)

        if news_ok and stock_ok:
            status = "success"
        elif news_ok or stock_ok:
            status = "partial"
        else:
            status = "failed"

        logger.info(
            f"[collector] Collection complete — "
            f"news={'✅' if news_ok else '❌'} "
            f"stock={'✅' if stock_ok else '❌'} "
            f"status={status}"
        )

        raw_data: CollectorOutput = {
            "company":       company,
            "news":          news_result.get("data", {}),
            "stock":         stock_result.get("data", {}),
            "news_source":   news_result.get("source", "unknown"),
            "stock_source":  stock_result.get("source", "unknown"),
            "collected_at":  datetime.now().isoformat(),
            "errors":        errors,
        }

        return {
            "raw_data":          raw_data,
            "collector_status":  status,
        }

    except Exception as e:
        logger.error(f"[collector] Fatal error: {e}")
        return {
            "raw_data":          None,
            "collector_status":  "failed",
            "error_message":     f"Collector agent crashed: {type(e).__name__}: {e}",
        }
"""
app/controller.py
──────────────────────────────────────────────────────────────
Production-grade controller layer that sits above the graph.

Responsibilities:
  • Assigns a unique run_id to every execution
  • Measures wall-clock execution time
  • Wraps graph.invoke() in retry logic
  • Returns a clean PipelineResult envelope
  • Logs a structured summary after every run

The graph knows nothing about retries or run IDs.
The UI knows nothing about LangGraph state.
The controller is the translation layer between them.
──────────────────────────────────────────────────────────────
"""

import uuid
import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

from graph.workflow import run_pipeline
from config.settings import settings
from config.logger import logger


# ─────────────────────────────────────────────────────────────
# RESULT ENVELOPE
# ─────────────────────────────────────────────────────────────

@dataclass
class PipelineResult:
    """
    Clean result object returned to the UI / API.
    Decouples consumers from LangGraph's internal state dict.
    """
    run_id:            str
    company:           str
    status:            str          # "complete" | "failed"
    final_report:      str          # Markdown report
    sentiment:         str          # "positive" | "neutral" | "negative"
    confidence:        str          # "high" | "medium" | "low"
    key_insights:      list[str]
    risk_factors:      list[str]
    summary:           str
    ticker:            str
    current_price:     Optional[float]
    change_pct:        Optional[float]
    market_cap:        str
    article_count:     int
    collector_status:  str
    analyst_status:    str
    news_source:       str
    stock_source:      str
    execution_time_s:  float
    executed_at:       str
    error_message:     Optional[str] = None
    attempts:          int = 1

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)

    @property
    def succeeded(self) -> bool:
        return self.status == "complete"


def _extract_result(state: dict, company: str, run_id: str,
                    elapsed: float, attempts: int) -> PipelineResult:
    """Unpacks LangGraph state into a clean PipelineResult."""
    analysis  = state.get("analysis") or {}
    raw_data  = state.get("raw_data") or {}
    stock     = raw_data.get("stock") or {}
    news      = raw_data.get("news")  or {}

    return PipelineResult(
        run_id           = run_id,
        company          = company,
        status           = state.get("pipeline_status", "failed"),
        final_report     = state.get("final_report", "No report generated."),
        sentiment        = analysis.get("sentiment", "unknown"),
        confidence       = analysis.get("confidence", "unknown"),
        key_insights     = analysis.get("key_insights", []),
        risk_factors     = analysis.get("risk_factors", []),
        summary          = analysis.get("summary", ""),
        ticker           = stock.get("ticker", "N/A"),
        current_price    = stock.get("current_price"),
        change_pct       = stock.get("change_pct"),
        market_cap       = stock.get("market_cap", "N/A"),
        article_count    = news.get("article_count", 0),
        collector_status = state.get("collector_status", "unknown"),
        analyst_status   = state.get("analyst_status", "unknown"),
        news_source      = raw_data.get("news_source", "unknown"),
        stock_source     = raw_data.get("stock_source", "unknown"),
        execution_time_s = round(elapsed, 2),
        executed_at      = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        error_message    = state.get("error_message"),
        attempts         = attempts,
    )


# ─────────────────────────────────────────────────────────────
# CONTROLLER
# ─────────────────────────────────────────────────────────────

class CompanyIntelController:
    """
    Orchestration controller for the Company Intelligence pipeline.

    Usage:
        controller = CompanyIntelController()
        result = controller.run("Tesla")
        print(result.final_report)
    """

    def __init__(self, max_retries: int = None):
        self.max_retries = max_retries or settings.max_retries

    def run(self, company: str) -> PipelineResult:
        """
        Executes the full pipeline with retry logic.

        On transient failures (network issues, rate limits),
        waits with exponential back-off before retrying.
        Permanent failures (bad company name, no data) are
        not retried — they fail fast on attempt 1.

        Args:
            company: Company name to analyze

        Returns:
            PipelineResult with all fields populated
        """
        run_id = str(uuid.uuid4())[:8].upper()
        company = company.strip()

        logger.info(f"[controller] ══ RUN {run_id} ══ company='{company}'")
        logger.info(f"[controller] Provider={settings.llm_provider} | "
                    f"Model={settings.active_model} | "
                    f"Mock={settings.use_mock_data}")

        start = time.time()
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                if attempt > 1:
                    wait = 2 ** (attempt - 2)   # 1s, 2s, 4s …
                    logger.warning(f"[controller] Retry {attempt}/{self.max_retries} "
                                   f"in {wait}s...")
                    time.sleep(wait)

                logger.info(f"[controller] Attempt {attempt} — invoking graph")
                state = run_pipeline(company)
                elapsed = time.time() - start

                result = _extract_result(state, company, run_id, elapsed, attempt)
                self._log_summary(result)
                return result

            except Exception as e:
                last_error = e
                elapsed = time.time() - start
                logger.error(f"[controller] Attempt {attempt} failed "
                             f"after {elapsed:.1f}s: {e}")

                # Don't retry validation / auth errors — they won't fix themselves
                err_str = str(e).lower()
                permanent = any(k in err_str for k in
                                ["invalid_api_key", "authentication", "not found",
                                 "invalid company"])
                if permanent:
                    logger.error("[controller] Permanent error — skipping retries")
                    break

        # All attempts exhausted
        elapsed = time.time() - start
        logger.error(f"[controller] ✗ RUN {run_id} FAILED after "
                     f"{self.max_retries} attempts ({elapsed:.1f}s)")

        return PipelineResult(
            run_id=run_id, company=company, status="failed",
            final_report=f"# ❌ Pipeline failed for {company}\n\n"
                         f"**Error:** {last_error}\n\n"
                         f"Check your API keys and try again.",
            sentiment="unknown", confidence="unknown",
            key_insights=[], risk_factors=[], summary="",
            ticker="N/A", current_price=None, change_pct=None,
            market_cap="N/A", article_count=0,
            collector_status="failed", analyst_status="failed",
            news_source="none", stock_source="none",
            execution_time_s=round(elapsed, 2),
            executed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            error_message=str(last_error),
            attempts=self.max_retries,
        )

    def _log_summary(self, r: PipelineResult):
        """Logs a one-line structured summary after every successful run."""
        status_icon = "✅" if r.succeeded else "❌"
        logger.info(
            f"[controller] {status_icon} RUN {r.run_id} COMPLETE | "
            f"company={r.company} | "
            f"status={r.status} | "
            f"sentiment={r.sentiment} | "
            f"confidence={r.confidence} | "
            f"time={r.execution_time_s}s | "
            f"attempts={r.attempts}"
        )


# ── Module-level singleton ────────────────────────────────────
# Import this anywhere: `from app.controller import controller`
controller = CompanyIntelController()
"""
agents/state.py
──────────────────────────────────────────────────────────────
Defines the shared state object that flows through the entire
LangGraph pipeline.

Why TypedDict?
  LangGraph requires state to be a TypedDict (or Pydantic model).
  TypedDict gives us type hints + dict behaviour — agents can
  read state["raw_data"] and write state["analysis"] naturally.

Design principle: Additive state.
  Each agent ADDS new keys to state. It never mutates keys
  written by a previous agent. This makes the pipeline easy
  to debug — you can inspect state at any point and see
  exactly what each agent contributed.

  START → state has: company
  After Collector → state adds: raw_data, collector_status
  After Analyst   → state adds: analysis, analyst_status
  After Final     → state adds: final_report
──────────────────────────────────────────────────────────────
"""

from typing import Optional
from typing_extensions import TypedDict


class CollectorOutput(TypedDict):
    """Structured output from the Data Collector agent."""
    company: str
    news: dict           # Full ToolResult.data from news_tool
    stock: dict          # Full ToolResult.data from stock_tool
    news_source: str     # "mock" | "live_api"
    stock_source: str    # "mock" | "live_api"
    collected_at: str    # ISO timestamp
    errors: list[str]    # Any non-fatal errors encountered


class AnalysisOutput(TypedDict):
    """Structured output from the Analyst agent."""
    summary: str              # 2-3 paragraph company overview
    key_insights: list[str]   # 3-5 bullet insights
    risk_factors: list[str]   # 3-5 bullet risks
    sentiment: str            # "positive" | "neutral" | "negative"
    confidence: str           # "high" | "medium" | "low"
    analyst_notes: str        # Any caveats or data quality notes


class CompanyIntelState(TypedDict):
    """
    Master state object for the Company Intelligence pipeline.

    Fields are Optional because the graph starts with only
    `company` set — all other fields are populated by agents
    as the graph executes.
    """
    # ── Input (set by user / orchestrator) ───────────────────
    company: str                           # e.g. "Tesla"

    # ── Collector output (set by Agent 1) ────────────────────
    raw_data: Optional[CollectorOutput]
    collector_status: Optional[str]        # "success" | "partial" | "failed"

    # ── Analyst output (set by Agent 2) ──────────────────────
    analysis: Optional[AnalysisOutput]
    analyst_status: Optional[str]          # "success" | "failed"

    # ── Final report (set by Orchestrator) ───────────────────
    final_report: Optional[str]            # Formatted markdown report
    pipeline_status: Optional[str]         # "complete" | "failed"
    error_message: Optional[str]           # Top-level error if pipeline fails


# ── Initial state factory ─────────────────────────────────────
def create_initial_state(company: str) -> CompanyIntelState:
    """
    Creates a fresh state dict for a new pipeline run.
    All Optional fields start as None — agents populate them.

    Usage:
        state = create_initial_state("Tesla")
        result = graph.invoke(state)
    """
    return CompanyIntelState(
        company=company,
        raw_data=None,
        collector_status=None,
        analysis=None,
        analyst_status=None,
        final_report=None,
        pipeline_status=None,
        error_message=None,
    )
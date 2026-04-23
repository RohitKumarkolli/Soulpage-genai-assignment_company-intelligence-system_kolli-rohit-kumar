"""
graph/workflow.py
──────────────────────────────────────────────────────────────
LangGraph orchestration — wires all agents into a compiled
StateGraph that runs with a single graph.invoke() call.

Graph topology:
  START
    ↓
  [data_collector_node]
    ↓
  {router} ──"failed"──→ [error_node] → END
    ↓ "ok"
  [analyst_node]
    ↓
  [final_report_node]
    ↓
  END
──────────────────────────────────────────────────────────────
"""

from datetime import datetime
from typing import Literal

from langgraph.graph import StateGraph, START, END

from agents.state import CompanyIntelState, create_initial_state
from agents.data_collector import data_collector_node
from agents.analyst import analyst_node
from config.logger import logger


# ─────────────────────────────────────────────────────────────
# NODE 3: Final Report Formatter
# ─────────────────────────────────────────────────────────────

def final_report_node(state: CompanyIntelState) -> dict:
    """
    Formats the analysis into a clean markdown intelligence report.
    This node has no LLM — it's pure formatting logic.

    Reads:  state["analysis"], state["raw_data"]
    Writes: state["final_report"], state["pipeline_status"]
    """
    company  = state.get("company", "Unknown")
    analysis = state.get("analysis", {})
    raw_data = state.get("raw_data", {})
    stock    = raw_data.get("stock", {}) if raw_data else {}
    news     = raw_data.get("news",  {}) if raw_data else {}

    logger.info(f"[final_report] Formatting report for '{company}'")

    if not analysis:
        return {
            "final_report": f"# ❌ Report generation failed for {company}\n\nNo analysis available.",
            "pipeline_status": "failed",
        }

    # ── Sentiment badge ───────────────────────────────────────
    sentiment_badge = {
        "positive": "🟢 POSITIVE",
        "neutral":  "🟡 NEUTRAL",
        "negative": "🔴 NEGATIVE",
    }.get(analysis.get("sentiment", "neutral"), "🟡 NEUTRAL")

    confidence_badge = {
        "high":   "⭐⭐⭐ HIGH",
        "medium": "⭐⭐ MEDIUM",
        "low":    "⭐ LOW",
    }.get(analysis.get("confidence", "low"), "⭐ LOW")

    # ── Stock summary line ────────────────────────────────────
    price      = stock.get("current_price", "N/A")
    change_pct = stock.get("change_pct", 0)
    ticker     = stock.get("ticker", "N/A")
    direction  = "▲" if float(change_pct or 0) >= 0 else "▼"
    stock_line = f"**{ticker}** | ${price} {direction} {change_pct}% | Cap: {stock.get('market_cap','N/A')} | P/E: {stock.get('pe_ratio','N/A')}"

    # ── News summary line ─────────────────────────────────────
    article_count = news.get("article_count", 0)
    date_range    = news.get("date_range", {})
    news_line     = f"{article_count} articles | {date_range.get('from','N/A')} → {date_range.get('to','N/A')}"

    # ── Key insights bullets ──────────────────────────────────
    insights_md = "\n".join(
        f"- {insight}" for insight in analysis.get("key_insights", [])
    )

    # ── Risk factors bullets ──────────────────────────────────
    risks_md = "\n".join(
        f"- {risk}" for risk in analysis.get("risk_factors", [])
    )

    # ── Assemble full markdown report ─────────────────────────
    report = f"""# 🏢 Company Intelligence Report: {company}

> Generated: {datetime.now().strftime("%B %d, %Y at %H:%M")}
> Sentiment: {sentiment_badge} | Confidence: {confidence_badge}

---

## 📈 Market Snapshot
{stock_line}

**News Coverage:** {news_line}

---

## 📋 Executive Summary

{analysis.get("summary", "No summary available.")}

---

## 💡 Key Insights

{insights_md}

---

## ⚠️ Risk Factors

{risks_md}

---

## 📝 Analyst Notes

> {analysis.get("analyst_notes", "No notes available.")}

---
*Data sources: news={raw_data.get('news_source','N/A')}, stock={raw_data.get('stock_source','N/A')}*
"""

    logger.info(f"[final_report] ✅ Report ready ({len(report)} chars)")
    return {
        "final_report": report,
        "pipeline_status": "complete",
    }


# ─────────────────────────────────────────────────────────────
# ERROR NODE
# ─────────────────────────────────────────────────────────────

def error_node(state: CompanyIntelState) -> dict:
    """
    Handles the case where the collector completely failed.
    Produces a user-friendly error report instead of crashing.
    """
    company = state.get("company", "Unknown")
    error   = state.get("error_message", "Unknown error")
    logger.error(f"[error_node] Pipeline failed for '{company}': {error}")
    report = f"""# ❌ Intelligence Report Failed: {company}

**Error:** {error}

**Suggestions:**
- Check your API keys in `.env`
- Verify internet connectivity
- Try again with `USE_MOCK_DATA=true` to test the pipeline
"""
    return {
        "final_report": report,
        "pipeline_status": "failed",
    }


# ─────────────────────────────────────────────────────────────
# CONDITIONAL ROUTER
# ─────────────────────────────────────────────────────────────

def route_after_collector(
    state: CompanyIntelState,
) -> Literal["analyst_node", "error_node"]:
    """
    Decides which node runs after the collector.

    LangGraph conditional edges call this function with the
    current state and route to whichever node name is returned.

    Returns:
      "analyst_node" → if collector got at least some data
      "error_node"   → if collector got nothing at all
    """
    status = state.get("collector_status", "failed")
    if status in ("success", "partial"):
        logger.info(f"[router] collector_status='{status}' → routing to analyst")
        return "analyst_node"
    else:
        logger.warning(f"[router] collector_status='{status}' → routing to error_node")
        return "error_node"


# ─────────────────────────────────────────────────────────────
# GRAPH BUILDER
# ─────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Constructs and compiles the full LangGraph pipeline.

    compile() validates:
      - All nodes referenced in edges actually exist
      - There are no unreachable nodes
      - START and END are properly connected
      - No cycles (unless explicitly added)

    Returns a compiled graph ready for invoke().
    """
    logger.info("[graph] Building Company Intelligence workflow...")

    # ── 1. Create graph with our shared state schema ──────────
    graph = StateGraph(CompanyIntelState)

    # ── 2. Register nodes ─────────────────────────────────────
    # Each node is a plain Python function that takes state
    # and returns a dict of state updates.
    graph.add_node("data_collector_node", data_collector_node)
    graph.add_node("analyst_node",        analyst_node)
    graph.add_node("final_report_node",   final_report_node)
    graph.add_node("error_node",          error_node)

    # ── 3. Connect edges ──────────────────────────────────────
    # START → collector (always)
    graph.add_edge(START, "data_collector_node")

    # collector → conditional branch (success/partial → analyst, failed → error)
    graph.add_conditional_edges(
        "data_collector_node",      # source node
        route_after_collector,      # routing function
        {                           # mapping: return value → node name
            "analyst_node": "analyst_node",
            "error_node":   "error_node",
        },
    )

    # analyst → final report (always)
    graph.add_edge("analyst_node", "final_report_node")

    # Both final_report and error_node → END
    graph.add_edge("final_report_node", END)
    graph.add_edge("error_node",        END)

    # ── 4. Compile ────────────────────────────────────────────
    compiled = graph.compile()
    logger.info("[graph] ✅ Graph compiled successfully")
    return compiled


# ─────────────────────────────────────────────────────────────
# PUBLIC INTERFACE
# ─────────────────────────────────────────────────────────────

def run_pipeline(company: str) -> CompanyIntelState:
    """
    Runs the full intelligence pipeline for a given company.

    This is the single entry point the app and UI will use.
    Everything else is internal graph wiring.

    Args:
        company: Company name (e.g. "Tesla", "Apple Inc")

    Returns:
        Final CompanyIntelState with all fields populated.
        Check state["pipeline_status"] for "complete" | "failed".
        Check state["final_report"] for the formatted markdown.
    """
    logger.info(f"[pipeline] ▶▶▶ Starting pipeline for '{company}'")
    start_time = datetime.now()

    graph  = build_graph()
    state  = create_initial_state(company)
    result = graph.invoke(state)

    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(
        f"[pipeline] ▶▶▶ Pipeline complete in {elapsed:.1f}s — "
        f"status={result.get('pipeline_status')}"
    )
    return result
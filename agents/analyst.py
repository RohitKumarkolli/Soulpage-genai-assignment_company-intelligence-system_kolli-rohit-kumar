"""
agents/analyst.py
──────────────────────────────────────────────────────────────
Agent 2: The Analyst

Responsibilities:
  1. Read raw_data from graph state (produced by Collector)
  2. Format data into a rich analytical prompt
  3. Call LLM with structured output schema (Pydantic)
  4. Parse and validate the LLM's response
  5. Write AnalysisOutput into graph state

Key patterns used here:
  • with_structured_output()  — forces the LLM to return JSON
                                that matches a Pydantic schema
  • Rule-based fallback        — if LLM/parsing fails, generate
                                a basic analysis from raw data
  • Prompt templating          — injects real data into prompts
                                at runtime for grounded analysis
──────────────────────────────────────────────────────────────
"""

import json
from datetime import datetime
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate
from config.llm_factory import build_llm
from pydantic import BaseModel, Field

from agents.state import CompanyIntelState, AnalysisOutput, CollectorOutput
from config.settings import settings
from config.logger import logger


# ─────────────────────────────────────────────────────────────
# PYDANTIC SCHEMA — Structured Output Contract
# ─────────────────────────────────────────────────────────────
# This schema does THREE things:
#   1. Tells the LLM exactly what fields to produce (via JSON schema)
#   2. Validates the LLM's response (Pydantic validation)
#   3. Serves as documentation for what the Analyst outputs
#
# with_structured_output(AnalysisSchema) passes this schema to
# OpenAI's function-calling API — the model is CONSTRAINED to
# return valid JSON matching this structure. No hallucinated
# fields, no missing fields.
# ─────────────────────────────────────────────────────────────

class AnalysisSchema(BaseModel):
    """
    Pydantic model enforcing the LLM's output structure.
    Field descriptions are injected into the JSON schema
    sent to the model — they guide the LLM's generation.
    """
    summary: str = Field(
        description=(
            "A 2-3 paragraph executive summary of the company's current "
            "situation based on recent news and financial data. "
            "Be specific — reference actual headlines and stock figures."
        )
    )
    key_insights: list[str] = Field(
        description=(
            "Exactly 4 key insights drawn from the data. Each insight should "
            "be 1-2 sentences, specific, and actionable. Format each as a "
            "complete sentence starting with the company name or 'The company'."
        ),
        min_length=3,
        max_length=6,
    )
    risk_factors: list[str] = Field(
        description=(
            "Exactly 4 risk factors identified from the data. Each risk should "
            "be 1-2 sentences explaining the risk and its potential impact. "
            "Include both news-based risks and financial/market risks."
        ),
        min_length=3,
        max_length=6,
    )
    sentiment: str = Field(
        description=(
            "Overall market sentiment based on news and stock movement. "
            "Must be exactly one of: 'positive', 'neutral', or 'negative'."
        )
    )
    confidence: str = Field(
        description=(
            "Confidence level in this analysis given data quality and quantity. "
            "Must be exactly one of: 'high', 'medium', or 'low'. "
            "Use 'low' if fewer than 3 news articles or stock data is missing."
        )
    )
    analyst_notes: str = Field(
        description=(
            "1-2 sentences noting any data limitations, caveats, or "
            "important context the reader should know. "
            "If mock data was used, note that findings are illustrative."
        )
    )


# ─────────────────────────────────────────────────────────────
# PROMPTS
# ─────────────────────────────────────────────────────────────
# Two-part prompt:
#   System: Establishes analyst persona and analytical framework
#   Human:  Injects the actual data at runtime
#
# Prompt engineering principles applied:
#   • Role definition    ("You are a senior financial analyst")
#   • Scope constraint   ("Base analysis ONLY on provided data")
#   • Output format      (explicit JSON field instructions)
#   • Grounding          (tell it to reference specific data points)
#   • Anti-hallucination ("Do not invent facts not in the data")
# ─────────────────────────────────────────────────────────────

ANALYST_SYSTEM_PROMPT = """You are a senior financial analyst at a top-tier investment bank.
You specialize in synthesizing news and market data into clear, actionable intelligence reports.

## Your Analytical Framework

When analyzing a company, you evaluate:
1. **Recent News Narrative** — What story are recent headlines telling?
   Are they predominantly positive, mixed, or negative?
2. **Financial Health Signals** — What does the stock data reveal?
   Consider price movement, P/E ratio, and market cap context.
3. **Strategic Position** — Based on news themes, where is the company headed?
   Look for patterns: expansion, regulatory pressure, innovation, cost-cutting.
4. **Risk Profile** — What could hurt this company in the near term?
   Separate market risks (macro) from company-specific risks.

## Strict Rules
- Base your analysis ONLY on the data provided — do not invent facts
- Reference specific headlines and financial figures in your summary
- Be direct and specific — avoid generic statements like "the company faces challenges"
- If data is limited or from mock sources, adjust confidence accordingly
- Sentiment must reflect the BALANCE of evidence, not just the most recent news

## Output
You will produce a structured JSON analysis following the exact schema provided."""


def _build_analyst_prompt(raw_data: CollectorOutput) -> str:
    """
    Builds the human prompt by injecting real collected data.

    This function is the 'prompt compiler' — it takes the
    structured CollectorOutput and formats it into a rich,
    readable prompt that gives the LLM maximum context.

    Why format data manually instead of dumping raw JSON?
    Because LLMs reason better on structured natural language
    than on deeply nested JSON. We highlight the signal.
    """
    company = raw_data.get("company", "Unknown Company")
    news_data = raw_data.get("news", {})
    stock_data = raw_data.get("stock", {})
    news_source = raw_data.get("news_source", "unknown")
    stock_source = raw_data.get("stock_source", "unknown")
    errors = raw_data.get("errors", [])

    # ── Format news section ───────────────────────────────────
    articles = news_data.get("articles", [])
    if articles:
        news_lines = []
        for i, a in enumerate(articles, 1):
            news_lines.append(
                f"  {i}. [{a.get('source', 'Unknown')} | {a.get('published_at', 'N/A')} "
                f"| sentiment: {a.get('sentiment_hint', 'neutral')}]\n"
                f"     HEADLINE: {a.get('title', 'N/A')}\n"
                f"     SUMMARY:  {a.get('description', 'N/A')}"
            )
        news_section = "\n".join(news_lines)
        news_header = (
            f"Data source: {news_source.upper()} | "
            f"Articles retrieved: {len(articles)} | "
            f"Date range: {news_data.get('date_range', {}).get('from', 'N/A')} "
            f"to {news_data.get('date_range', {}).get('to', 'N/A')}"
        )
    else:
        news_section = "  NO NEWS DATA AVAILABLE"
        news_header = "Data source: UNAVAILABLE"

    # ── Format stock section ──────────────────────────────────
    if stock_data:
        price = stock_data.get("current_price", "N/A")
        change_pct = stock_data.get("change_pct", 0)
        change_dir = "▲" if float(change_pct or 0) >= 0 else "▼"
        stock_section = f"""  Data source: {stock_source.upper()}
  Ticker:           {stock_data.get('ticker', 'N/A')}
  Current Price:    ${price}  {change_dir} {change_pct}% (day)
  Previous Close:   ${stock_data.get('previous_close', 'N/A')}
  Market Cap:       {stock_data.get('market_cap', 'N/A')}
  P/E Ratio:        {stock_data.get('pe_ratio', 'N/A')}
  52-Week High:     ${stock_data.get('52_week_high', 'N/A')}
  52-Week Low:      ${stock_data.get('52_week_low', 'N/A')}
  Sector:           {stock_data.get('sector', 'N/A')}
  As of:            {stock_data.get('as_of', 'N/A')}"""
    else:
        stock_section = "  STOCK DATA UNAVAILABLE"

    # ── Format data quality notes ─────────────────────────────
    quality_notes = []
    if news_source == "mock":
        quality_notes.append("⚠ News data is MOCK/SIMULATED — for illustrative purposes only")
    if stock_source == "mock":
        quality_notes.append("⚠ Stock data is MOCK/SIMULATED — prices are not real")
    if errors:
        quality_notes.append(f"⚠ Collection errors: {'; '.join(errors)}")
    quality_section = (
        "\n".join(f"  {n}" for n in quality_notes)
        if quality_notes else "  All data sources returned successfully"
    )

    return f"""Analyze the following company intelligence data and produce a structured report.

═══════════════════════════════════════════════════════════
COMPANY: {company}
ANALYSIS DATE: {datetime.now().strftime("%B %d, %Y")}
═══════════════════════════════════════════════════════════

── SECTION 1: RECENT NEWS ──────────────────────────────────
{news_header}

{news_section}

── SECTION 2: FINANCIAL DATA ───────────────────────────────
{stock_section}

── SECTION 3: DATA QUALITY NOTES ───────────────────────────
{quality_section}
═══════════════════════════════════════════════════════════

Using the framework in your instructions, produce a complete
structured analysis of {company}. Reference specific data
points from both sections above."""


# ─────────────────────────────────────────────────────────────
# RULE-BASED FALLBACK ANALYSER
# ─────────────────────────────────────────────────────────────
# If the LLM is unavailable OR structured output parsing fails,
# this function generates a basic but valid AnalysisOutput
# from the raw data using pure Python logic.
#
# Why have a fallback?
#   In production, LLMs occasionally fail or return malformed
#   output. The graph must never stall — it should always
#   produce SOMETHING the user can read.
# ─────────────────────────────────────────────────────────────

def _rule_based_analysis(raw_data: CollectorOutput) -> AnalysisOutput:
    """
    Generates a deterministic analysis from raw data without LLM.
    Used as fallback when OpenAI is unavailable or parsing fails.
    """
    logger.info("[analyst] Running rule-based fallback analysis")

    company = raw_data.get("company", "The company")
    news = raw_data.get("news", {})
    stock = raw_data.get("stock", {})
    articles = news.get("articles", [])
    news_source = raw_data.get("news_source", "unknown")
    stock_source = raw_data.get("stock_source", "unknown")

    # ── Derive sentiment from article hints ───────────────────
    sentiments = [a.get("sentiment_hint", "neutral") for a in articles]
    pos = sentiments.count("positive")
    neg = sentiments.count("negative")
    if pos > neg + 1:
        overall_sentiment = "positive"
    elif neg > pos + 1:
        overall_sentiment = "negative"
    else:
        overall_sentiment = "neutral"

    # ── Build summary ─────────────────────────────────────────
    price = stock.get("current_price", "N/A")
    ticker = stock.get("ticker", "N/A")
    change = stock.get("change_pct", 0)
    change_str = f"up {change}%" if float(change or 0) >= 0 else f"down {abs(float(change or 0))}%"
    mkt_cap = stock.get("market_cap", "N/A")

    summary = (
        f"{company} ({ticker}) is currently trading at ${price}, {change_str} on the day, "
        f"with a market capitalization of {mkt_cap}. "
        f"Based on {len(articles)} recent news articles, the overall news sentiment "
        f"is {overall_sentiment}, with {pos} positive and {neg} negative signals detected.\n\n"
        f"The company operates in the {stock.get('sector', 'N/A')} sector. "
        f"Its P/E ratio of {stock.get('pe_ratio', 'N/A')} and "
        f"52-week range of ${stock.get('52_week_low', 'N/A')}–${stock.get('52_week_high', 'N/A')} "
        f"provide context for valuation. "
        f"Note: This is an automated rule-based analysis — LLM analysis was unavailable."
    )

    # ── Build insights from top articles ─────────────────────
    key_insights = []
    for a in articles[:4]:
        headline = a.get("title", "")
        sentiment = a.get("sentiment_hint", "neutral")
        key_insights.append(
            f"{company}: {headline[:80]}{'...' if len(headline) > 80 else ''} "
            f"(Signal: {sentiment})"
        )
    if not key_insights:
        key_insights = [f"{company} stock data collected but no news articles available."]

    # Always add a financial insight
    key_insights.append(
        f"{company} is trading at ${price} with a {change_str} daily movement, "
        f"suggesting {'bullish' if float(change or 0) >= 0 else 'bearish'} short-term momentum."
    )

    # ── Build risk factors ────────────────────────────────────
    risk_factors = []
    neg_articles = [a for a in articles if a.get("sentiment_hint") == "negative"]
    for a in neg_articles[:3]:
        risk_factors.append(
            f"News risk: {a.get('title', '')[:80]} — "
            f"reported by {a.get('source', 'Unknown')} on {a.get('published_at', 'N/A')}."
        )
    # Always add standard financial risks
    risk_factors.append(
        f"Market risk: At a P/E ratio of {stock.get('pe_ratio', 'N/A')}, "
        f"{company} may face valuation pressure if earnings disappoint."
    )
    risk_factors.append(
        f"Data risk: Analysis based on {news_source}/{stock_source} data sources. "
        f"Real-time intelligence may differ materially."
    )
    if not risk_factors:
        risk_factors = [f"No specific risk signals detected in available data for {company}."]

    return AnalysisOutput(
        summary=summary,
        key_insights=key_insights[:5],
        risk_factors=risk_factors[:5],
        sentiment=overall_sentiment,
        confidence="low",        # Rule-based is always lower confidence
        analyst_notes=(
            f"This analysis was generated using rule-based logic (LLM unavailable). "
            f"Data sources: news={news_source}, stock={stock_source}. "
            f"For higher-quality analysis, configure OPENAI_API_KEY."
        ),
    )


# ─────────────────────────────────────────────────────────────
# LLM ANALYSER
# ─────────────────────────────────────────────────────────────

def _run_llm_analysis(raw_data: CollectorOutput) -> AnalysisOutput:
    """
    Runs the LLM-powered analysis using structured output.

    with_structured_output(AnalysisSchema) does the heavy lifting:
      1. Converts AnalysisSchema to OpenAI function-call JSON schema
      2. Forces the model to call that function with valid args
      3. Parses the response back into an AnalysisSchema instance
      4. Raises OutputParserException if parsing fails

    This is far more reliable than asking the LLM to "output JSON"
    and then manually parsing — that approach has ~15% failure rate.
    Function-calling has <1% failure rate.
    """
    logger.info(f"[analyst] Running LLM analysis for '{raw_data.get('company')}'")

    # temperature=0.2: slight creativity for narrative prose
    # Provider (Groq/OpenAI) is set via LLM_PROVIDER in .env
    llm = build_llm(temperature=0.2)

    # Bind structured output schema — this is the key line
    structured_llm = llm.with_structured_output(AnalysisSchema)

    # Build runtime prompt with actual data injected
    prompt = ChatPromptTemplate.from_messages([
        ("system", ANALYST_SYSTEM_PROMPT),
        ("human", "{data_prompt}"),
    ])

    # Chain: prompt | structured_llm
    # The pipe operator (|) creates a LangChain LCEL chain.
    # prompt formats the messages → structured_llm calls OpenAI
    # and returns a validated AnalysisSchema instance.
    chain = prompt | structured_llm

    data_prompt = _build_analyst_prompt(raw_data)
    logger.debug(f"[analyst] Prompt length: {len(data_prompt)} chars")

    result: AnalysisSchema = chain.invoke({"data_prompt": data_prompt})

    # Validate sentiment and confidence are legal values
    valid_sentiments = {"positive", "neutral", "negative"}
    valid_confidences = {"high", "medium", "low"}

    sentiment = result.sentiment.lower().strip()
    if sentiment not in valid_sentiments:
        logger.warning(f"[analyst] Invalid sentiment '{sentiment}', defaulting to 'neutral'")
        sentiment = "neutral"

    confidence = result.confidence.lower().strip()
    if confidence not in valid_confidences:
        logger.warning(f"[analyst] Invalid confidence '{confidence}', defaulting to 'medium'")
        confidence = "medium"

    return AnalysisOutput(
        summary=result.summary,
        key_insights=result.key_insights,
        risk_factors=result.risk_factors,
        sentiment=sentiment,
        confidence=confidence,
        analyst_notes=result.analyst_notes,
    )


# ─────────────────────────────────────────────────────────────
# NODE FUNCTION — This is what LangGraph calls
# ─────────────────────────────────────────────────────────────

def analyst_node(state: CompanyIntelState) -> dict:
    """
    LangGraph node for the Analyst agent.

    Reads:  state["raw_data"], state["collector_status"]
    Writes: state["analysis"], state["analyst_status"]

    Routing logic:
      • collector_status == "failed"  → skip LLM, mark analyst failed
      • collector_status == "partial" → run analysis with a data warning
      • collector_status == "success" → full analysis

    Execution logic:
      • has_openai_key AND not mock mode → LLM analysis
      • otherwise → rule-based fallback
    """
    company = state.get("company", "Unknown")
    collector_status = state.get("collector_status", "failed")
    raw_data = state.get("raw_data")

    logger.info(
        f"[analyst] ▶ Starting analysis for '{company}' "
        f"(collector_status={collector_status})"
    )

    # ── Guard: no data to analyze ─────────────────────────────
    if collector_status == "failed" or raw_data is None:
        logger.error("[analyst] No data available — collector failed")
        return {
            "analysis": None,
            "analyst_status": "failed",
            "error_message": "Analyst skipped: collector returned no data",
        }

    try:
        # Choose LLM vs rule-based based on config
        use_llm = settings.has_llm_key and not settings.use_mock_data

        if use_llm:
            try:
                analysis = _run_llm_analysis(raw_data)
                logger.info(
                    f"[analyst] LLM analysis complete — "
                    f"sentiment={analysis['sentiment']} "
                    f"confidence={analysis['confidence']}"
                )
            except Exception as llm_error:
                # LLM failed — fall back to rule-based gracefully
                logger.warning(
                    f"[analyst] LLM analysis failed ({llm_error}), "
                    f"falling back to rule-based"
                )
                analysis = _rule_based_analysis(raw_data)
        else:
            # Direct mock / no-key mode
            analysis = _rule_based_analysis(raw_data)
            logger.info(
                f"[analyst] Rule-based analysis complete — "
                f"sentiment={analysis['sentiment']} "
                f"confidence={analysis['confidence']}"
            )

        # ── Downgrade confidence for partial data ─────────────
        if collector_status == "partial":
            original = analysis["confidence"]
            downgrade = {"high": "medium", "medium": "low", "low": "low"}
            analysis["confidence"] = downgrade.get(original, "low")
            analysis["analyst_notes"] += (
                " Note: Confidence downgraded due to partial data collection."
            )
            logger.info(f"[analyst] Confidence downgraded: {original} → {analysis['confidence']}")

        return {
            "analysis": analysis,
            "analyst_status": "success",
        }

    except Exception as e:
        logger.error(f"[analyst] Fatal error: {e}")
        return {
            "analysis": None,
            "analyst_status": "failed",
            "error_message": f"Analyst agent crashed: {type(e).__name__}: {e}",
        }
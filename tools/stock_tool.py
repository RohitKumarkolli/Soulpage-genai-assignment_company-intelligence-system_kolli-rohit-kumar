"""
tools/stock_tool.py
──────────────────────────────────────────────────────────────
Fetches stock price and financial summary data for a company.

Live mode:  Uses Alpha Vantage API (https://www.alphavantage.co)
            Free tier: 25 requests/day
Mock mode:  Returns realistic pre-built financial data

Includes a company→ticker symbol resolver so the agent can
pass "Apple Inc" instead of having to know "AAPL".
──────────────────────────────────────────────────────────────
"""

import random
from datetime import datetime, timedelta
from langchain_core.tools import tool

from config.settings import settings
from config.logger import logger
from tools.base import ToolResult, safe_tool_call, retry_request


# ── Ticker Symbol Resolver ────────────────────────────────────
# Maps common company names → stock tickers.
# In production you'd query a proper symbol search API.
TICKER_MAP: dict[str, str] = {
    "apple": "AAPL",
    "apple inc": "AAPL",
    "microsoft": "MSFT",
    "microsoft corporation": "MSFT",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "alphabet inc": "GOOGL",
    "amazon": "AMZN",
    "amazon.com": "AMZN",
    "meta": "META",
    "meta platforms": "META",
    "facebook": "META",
    "tesla": "TSLA",
    "tesla inc": "TSLA",
    "nvidia": "NVDA",
    "nvidia corporation": "NVDA",
    "netflix": "NFLX",
    "salesforce": "CRM",
    "adobe": "ADBE",
    "intel": "INTC",
    "amd": "AMD",
    "advanced micro devices": "AMD",
}

# ── Mock Stock Profiles ───────────────────────────────────────
# Realistic financial data per ticker.
# Each value is (base, volatility_pct) — mock adds slight randomness
# to make successive calls feel realistic.
MOCK_STOCK_PROFILES: dict[str, dict] = {
    "AAPL": {"price": 189.50, "change_pct": 1.2,  "market_cap": "2.95T", "pe_ratio": 31.2, "sector": "Technology"},
    "MSFT": {"price": 415.80, "change_pct": 0.8,  "market_cap": "3.09T", "pe_ratio": 36.1, "sector": "Technology"},
    "GOOGL": {"price": 175.30, "change_pct": -0.5, "market_cap": "2.18T", "pe_ratio": 24.8, "sector": "Technology"},
    "AMZN": {"price": 195.20, "change_pct": 1.5,  "market_cap": "2.05T", "pe_ratio": 44.5, "sector": "Consumer Discretionary"},
    "META": {"price": 528.40, "change_pct": 2.1,  "market_cap": "1.35T", "pe_ratio": 28.3, "sector": "Technology"},
    "TSLA": {"price": 248.50, "change_pct": -1.8, "market_cap": "792B",  "pe_ratio": 72.4, "sector": "Consumer Discretionary"},
    "NVDA": {"price": 875.40, "change_pct": 3.2,  "market_cap": "2.16T", "pe_ratio": 68.7, "sector": "Technology"},
    "NFLX": {"price": 628.90, "change_pct": 0.4,  "market_cap": "273B",  "pe_ratio": 45.2, "sector": "Communication Services"},
    "DEFAULT": {"price": 150.00, "change_pct": 0.5, "market_cap": "50B",  "pe_ratio": 22.0, "sector": "Diversified"},
}


def _resolve_ticker(company: str) -> str:
    """
    Resolves a company name to its ticker symbol.
    Falls back to using the company name itself as the ticker
    (useful for direct ticker inputs like 'AAPL').
    """
    normalized = company.lower().strip()
    if normalized in TICKER_MAP:
        ticker = TICKER_MAP[normalized]
        logger.debug(f"[stock_tool] Resolved '{company}' → {ticker}")
        return ticker
    # Could be a direct ticker already (e.g. "AAPL")
    upper = company.upper().strip()
    logger.debug(f"[stock_tool] No mapping for '{company}', using '{upper}' as ticker")
    return upper


def _generate_price_history(base_price: float, days: int = 5) -> list[dict]:
    """
    Generates a short mock OHLC price history for charting.
    Uses a simple random walk from the base price.
    """
    history = []
    price = base_price * 0.95   # Start slightly below current
    for i in range(days, 0, -1):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        open_p = round(price * (1 + random.uniform(-0.01, 0.01)), 2)
        close_p = round(open_p * (1 + random.uniform(-0.02, 0.02)), 2)
        high_p = round(max(open_p, close_p) * (1 + random.uniform(0, 0.01)), 2)
        low_p = round(min(open_p, close_p) * (1 - random.uniform(0, 0.01)), 2)
        history.append({
            "date": date,
            "open": open_p,
            "high": high_p,
            "low": low_p,
            "close": close_p,
            "volume": random.randint(20_000_000, 80_000_000),
        })
        price = close_p
    return history


def _get_mock_stock(company: str) -> ToolResult:
    """Returns mock stock data for any company."""
    logger.info(f"[stock_tool] Using mock data for '{company}'")
    ticker = _resolve_ticker(company)
    profile = MOCK_STOCK_PROFILES.get(ticker, MOCK_STOCK_PROFILES["DEFAULT"])

    # Add small randomness so results feel dynamic
    price = round(profile["price"] * (1 + random.uniform(-0.02, 0.02)), 2)
    prev_close = round(price / (1 + profile["change_pct"] / 100), 2)
    change = round(price - prev_close, 2)
    change_pct = round(profile["change_pct"] + random.uniform(-0.3, 0.3), 2)

    return ToolResult(
        success=True,
        source="mock",
        data={
            "company": company,
            "ticker": ticker,
            "current_price": price,
            "previous_close": prev_close,
            "change": change,
            "change_pct": change_pct,
            "market_cap": profile["market_cap"],
            "pe_ratio": profile["pe_ratio"],
            "sector": profile["sector"],
            "52_week_high": round(price * 1.28, 2),
            "52_week_low": round(price * 0.74, 2),
            "avg_volume": "45.2M",
            "price_history": _generate_price_history(price),
            "as_of": datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
        metadata={"mode": "mock", "ticker_resolved": ticker != company.upper()},
    )


def _get_live_stock(company: str) -> ToolResult:
    """Fetches real stock data from Alpha Vantage."""
    logger.info(f"[stock_tool] Fetching live stock data for '{company}'")
    ticker = _resolve_ticker(company)

    # Alpha Vantage: Global Quote endpoint
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": ticker,
        "apikey": settings.alpha_vantage_api_key,
    }
    response = retry_request(url, params=params)
    data = response.json()

    quote = data.get("Global Quote", {})
    if not quote or "05. price" not in quote:
        logger.warning(f"[stock_tool] No data for {ticker}, falling back to mock")
        return _get_mock_stock(company)

    price = float(quote.get("05. price", 0))
    prev_close = float(quote.get("08. previous close", 0))

    return ToolResult(
        success=True,
        source="live_api",
        data={
            "company": company,
            "ticker": ticker,
            "current_price": round(price, 2),
            "previous_close": round(prev_close, 2),
            "change": round(float(quote.get("09. change", 0)), 2),
            "change_pct": round(float(quote.get("10. change percent", "0%").replace("%", "")), 2),
            "market_cap": "N/A (use premium API)",
            "pe_ratio": "N/A (use premium API)",
            "sector": "N/A",
            "52_week_high": round(float(quote.get("03. high", price * 1.3)), 2),
            "52_week_low": round(float(quote.get("04. low", price * 0.7)), 2),
            "avg_volume": quote.get("06. volume", "N/A"),
            "price_history": [],   # Requires separate API call on free tier
            "as_of": quote.get("07. latest trading day", datetime.now().strftime("%Y-%m-%d")),
        },
        metadata={"ticker_resolved": ticker},
    )


@tool
@safe_tool_call
def fetch_stock_data(company: str) -> dict:
    """
    Fetches current stock price and key financial metrics for a company.

    Use this tool to get the current stock price, market cap, P/E ratio,
    52-week range, and recent price history for a publicly traded company.
    Automatically resolves company names to ticker symbols.

    Args:
        company: Company name or ticker symbol
                 (e.g. 'Apple Inc', 'Tesla', 'MSFT', 'Amazon')

    Returns:
        dict with keys:
          - success (bool)
          - data.ticker (str)
          - data.current_price (float)
          - data.change_pct (float)
          - data.market_cap (str)
          - data.pe_ratio (float)
          - data.52_week_high / 52_week_low (float)
          - data.price_history (list of OHLC dicts)
          - source ('mock' | 'live_api')
          - error (str, empty on success)
    """
    if settings.use_mock_data or not settings.alpha_vantage_api_key:
        return _get_mock_stock(company)
    return _get_live_stock(company)
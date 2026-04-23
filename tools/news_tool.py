"""
tools/news_tool.py
──────────────────────────────────────────────────────────────
Fetches recent news articles about a company.

Live mode:  Uses NewsAPI (https://newsapi.org)
            Free tier: 100 requests/day, 1-month history
Mock mode:  Returns realistic pre-built data — no API key needed

The @tool decorator exposes this to LangGraph agents.
The docstring IS the tool description the LLM reads — write it
carefully, it directly affects agent decision-making.
──────────────────────────────────────────────────────────────
"""

from datetime import datetime, timedelta
from langchain_core.tools import tool

from config.settings import settings
from config.logger import logger
from tools.base import ToolResult, safe_tool_call, retry_request


# ── Mock Data ─────────────────────────────────────────────────
MOCK_NEWS_DB: dict = {
    "default": [
        {
            "title": "{company} Reports Strong Quarterly Earnings, Beats Analyst Expectations",
            "source": "Reuters",
            "published_at": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
            "description": (
                "{company} exceeded Wall Street estimates with a 15% revenue increase, "
                "driven by robust demand across its core product lines and expanding "
                "international markets."
            ),
            "url": "https://reuters.com/mock/earnings",
            "sentiment_hint": "positive",
        },
        {
            "title": "{company} Faces Regulatory Scrutiny Over Data Privacy Practices",
            "source": "Bloomberg",
            "published_at": (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"),
            "description": (
                "Regulators in the EU have opened a preliminary inquiry into {company}'s "
                "data collection practices, citing potential violations of GDPR. "
                "The company has stated it is fully cooperating."
            ),
            "url": "https://bloomberg.com/mock/regulatory",
            "sentiment_hint": "negative",
        },
        {
            "title": "{company} Announces Strategic Partnership with Leading AI Firm",
            "source": "TechCrunch",
            "published_at": (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"),
            "description": (
                "{company} has signed a multi-year agreement to integrate advanced AI "
                "capabilities into its flagship products, signaling a significant push "
                "into the artificial intelligence space."
            ),
            "url": "https://techcrunch.com/mock/partnership",
            "sentiment_hint": "positive",
        },
        {
            "title": "{company} Expands into Emerging Markets with New Regional HQ",
            "source": "Financial Times",
            "published_at": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
            "description": (
                "As part of its 2025 growth strategy, {company} is establishing a new "
                "regional headquarters in Southeast Asia, targeting 200M+ new customers "
                "and hiring 5,000 local employees over the next 3 years."
            ),
            "url": "https://ft.com/mock/expansion",
            "sentiment_hint": "positive",
        },
        {
            "title": "{company} Supply Chain Disruptions Impact Q3 Production Targets",
            "source": "WSJ",
            "published_at": (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d"),
            "description": (
                "Ongoing supply chain challenges have forced {company} to revise its "
                "Q3 production targets downward by 8%, according to an internal memo "
                "cited by sources familiar with the matter."
            ),
            "url": "https://wsj.com/mock/supply-chain",
            "sentiment_hint": "negative",
        },
    ]
}


def _get_mock_news(company: str) -> ToolResult:
    """Returns mock news data with the company name injected."""
    logger.info(f"[news_tool] Using mock data for '{company}'")
    articles = []
    for template in MOCK_NEWS_DB["default"]:
        article = {k: v.replace("{company}", company) if isinstance(v, str) else v
                   for k, v in template.items()}
        articles.append(article)

    return ToolResult(
        success=True,
        source="mock",
        data={
            "company": company,
            "article_count": len(articles),
            "articles": articles,
            "date_range": {
                "from": (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d"),
                "to": datetime.now().strftime("%Y-%m-%d"),
            },
        },
        metadata={"mode": "mock"},
    )


def _get_live_news(company: str) -> ToolResult:
    """Fetches real news from NewsAPI."""
    logger.info(f"[news_tool] Fetching live news for '{company}'")
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": company,
        "apiKey": settings.news_api_key,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 5,
        "from": (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d"),
    }
    response = retry_request(url, params=params)
    data = response.json()
    if data.get("status") != "ok":
        return ToolResult.failure(
            error=f"NewsAPI error: {data.get('message', 'unknown')}",
            source="live_api",
        )
    raw_articles = data.get("articles", [])
    articles = [
        {
            "title": a.get("title", ""),
            "source": a.get("source", {}).get("name", "Unknown"),
            "published_at": a.get("publishedAt", "")[:10],
            "description": a.get("description", ""),
            "url": a.get("url", ""),
            "sentiment_hint": "neutral",
        }
        for a in raw_articles
        if a.get("title") and "[Removed]" not in a.get("title", "")
    ]
    logger.info(f"[news_tool] Retrieved {len(articles)} articles for '{company}'")
    return ToolResult(
        success=True,
        source="live_api",
        data={
            "company": company,
            "article_count": len(articles),
            "articles": articles,
            "date_range": {
                "from": params["from"],
                "to": datetime.now().strftime("%Y-%m-%d"),
            },
        },
        metadata={"total_results": data.get("totalResults", 0)},
    )


@tool
@safe_tool_call
def fetch_company_news(company: str) -> dict:
    """
    Fetches recent news articles about a company.

    Use this tool to get the latest news, announcements, and
    media coverage for a company. Returns up to 5 articles
    from the past 14 days, including title, source, date,
    and a brief description.

    Args:
        company: Full company name (e.g. 'Apple Inc', 'Tesla', 'Microsoft')

    Returns:
        dict with keys:
          - success (bool)
          - data.company (str)
          - data.articles (list of article dicts)
          - data.article_count (int)
          - data.date_range (dict)
          - source ('mock' | 'live_api')
          - error (str, empty on success)
    """
    if settings.use_mock_data or not settings.has_news_api_key:
        return _get_mock_news(company)
    return _get_live_news(company)
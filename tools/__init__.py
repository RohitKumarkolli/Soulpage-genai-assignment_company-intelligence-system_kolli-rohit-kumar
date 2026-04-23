
from tools.news_tool import fetch_company_news
from tools.stock_tool import fetch_stock_data

# Convenience list — pass directly to LangGraph agent node
ALL_TOOLS = [fetch_company_news, fetch_stock_data]

__all__ = ["fetch_company_news", "fetch_stock_data", "ALL_TOOLS"]

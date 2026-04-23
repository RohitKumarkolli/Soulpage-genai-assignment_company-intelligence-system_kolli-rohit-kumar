import json
from tools import fetch_company_news, fetch_stock_data

print("=" * 55)
print("TEST 1: fetch_company_news('Tesla')")
print("=" * 55)

result = fetch_company_news.invoke({'company': 'Tesla'})

print(f"Success : {result['success']}")
print(f"Source  : {result['source']}")
print(f"Articles: {result['data']['article_count']}")

print()

for i, a in enumerate(result['data']['articles'][:2], 1):
    print(f"[{i}] {a['title'][:60]}...")
    print(f"     {a['source']} | {a['published_at']} | {a['sentiment_hint']}")
    
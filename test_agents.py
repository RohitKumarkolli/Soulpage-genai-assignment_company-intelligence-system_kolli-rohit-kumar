"""
test_agents.py — Full pipeline integration test
Run: python test_agents.py
"""
import textwrap, sys
from agents.state import create_initial_state
from agents.data_collector import data_collector_node
from agents.analyst import analyst_node
from config.settings import settings

DIVIDER = '═' * 60

def wrap(text, width=56, indent='    '):
    return textwrap.fill(str(text), width=width,
                         initial_indent=indent,
                         subsequent_indent=indent)

def display_analysis(company, analysis):
    if not analysis:
        print("    ⚠ No analysis produced.")
        return
    print(f'\n{DIVIDER}')
    print(f'  COMPANY INTELLIGENCE REPORT')
    print(f'  Company   : {company}')
    print(f'  Sentiment : {analysis["sentiment"].upper()}')
    print(f'  Confidence: {analysis["confidence"].upper()}')
    print(DIVIDER)
    print('\n  ── EXECUTIVE SUMMARY ──────────────────────────────')
    for para in analysis['summary'].split('\n\n'):
        if para.strip():
            print(wrap(para.strip()))
            print()
    print('  ── KEY INSIGHTS ───────────────────────────────────')
    for i, insight in enumerate(analysis['key_insights'], 1):
        print(wrap(f'{i}. {insight}'))
        print()
    print('  ── RISK FACTORS ───────────────────────────────────')
    for i, risk in enumerate(analysis['risk_factors'], 1):
        print(wrap(f'{i}. {risk}'))
        print()
    print('  ── ANALYST NOTES ──────────────────────────────────')
    print(wrap(analysis['analyst_notes']))
    print()

# ── Print config summary ──────────────────────────────────────
print(f'\n{DIVIDER}')
print(f'  CONFIG CHECK')
print(DIVIDER)
print(f'  LLM Provider   : {settings.llm_provider.upper()}')
print(f'  Active Model   : {settings.active_model}')
print(f'  LLM Key set    : {settings.has_llm_key}')
print(f'  Mock mode      : {settings.use_mock_data}')
use_llm = settings.has_llm_key and not settings.use_mock_data
print(f'  LLM active     : {use_llm}')
if not use_llm:
    provider = settings.llm_provider.upper()
    print(f'  ⚠  Running in rule-based mode.')
    if not settings.has_llm_key:
        if settings.llm_provider == "groq":
            print('     Fix: Set GROQ_API_KEY=gsk_... in .env (free at console.groq.com)')
        else:
            print('     Fix: Set OPENAI_API_KEY=sk-... in .env')
    if settings.use_mock_data:
        print('     Fix: Set USE_MOCK_DATA=false in .env')
else:
    print(f'  ✅ {settings.llm_provider.upper()} LLM ready — {settings.active_model}')

# ── TEST 1: Full pipeline ─────────────────────────────────────
print(f'\n{DIVIDER}')
print('  TEST 1 — Full pipeline: Collector → Analyst (Tesla)')
print(DIVIDER)

state = create_initial_state('Tesla')
state.update(data_collector_node(state))

collector_ok = state['collector_status'] != 'failed' and state['raw_data']
print(f'  Collector  → status={state["collector_status"]}')

if collector_ok:
    print(f'               news articles={state["raw_data"]["news"].get("article_count", 0)}')
    print(f'               stock ticker ={state["raw_data"]["stock"].get("ticker", "N/A")}')
    state.update(analyst_node(state))
    print(f'  Analyst    → status={state["analyst_status"]}')
    display_analysis('Tesla', state.get('analysis'))
else:
    err = state.get('error_message', 'unknown error')
    print(f'  ❌ Collector failed: {err}')
    print(f'  ⏭  Skipping analyst — no data to analyze')

# ── TEST 2: Partial data ──────────────────────────────────────
print(DIVIDER)
print('  TEST 2 — Partial data (confidence downgrade)')
print(DIVIDER)

state2 = create_initial_state('Microsoft')
state2.update(data_collector_node(state2))
if state2['raw_data']:
    state2['collector_status'] = 'partial'
    state2['raw_data']['stock'] = {}        # Simulate missing stock
state2.update(analyst_node(state2))
print(f'  Collector  → status=partial (simulated)')
print(f'  Analyst    → status={state2["analyst_status"]}')
if state2.get('analysis'):
    print(f'  Confidence → {state2["analysis"]["confidence"]} (downgraded)')
    print(f'  Sentiment  → {state2["analysis"]["sentiment"]}')

# ── TEST 3: Collector failure guard ──────────────────────────
print(f'\n{DIVIDER}')
print('  TEST 3 — Collector failed → Analyst skips gracefully')
print(DIVIDER)

state3 = create_initial_state('NVIDIA')
state3['collector_status'] = 'failed'
state3['raw_data'] = None
state3.update(analyst_node(state3))
print(f'  Analyst status  : {state3["analyst_status"]}')
print(f'  Analysis        : {state3["analysis"]}')
print(f'  Error message   : {state3.get("error_message")}')

# ── TEST 4: All fields present ───────────────────────────────
print(f'\n{DIVIDER}')
print('  TEST 4 — NVIDIA: Verify all output fields')
print(DIVIDER)

state4 = create_initial_state('NVIDIA')
state4.update(data_collector_node(state4))
state4.update(analyst_node(state4))
analysis = state4.get('analysis') or {}
for field in ['summary','key_insights','risk_factors','sentiment','confidence','analyst_notes']:
    val = analysis.get(field)
    ok = '✅' if val else '❌'
    if isinstance(val, list):
        print(f'  {ok} {field}: {len(val)} items')
    elif isinstance(val, str):
        preview = val[:45] + '...' if len(val) > 45 else val
        print(f'  {ok} {field}: "{preview}"')

print(f'\n✅ All tests completed (LLM mode: {use_llm})')
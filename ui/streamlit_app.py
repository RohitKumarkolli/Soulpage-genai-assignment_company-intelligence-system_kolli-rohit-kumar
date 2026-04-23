"""
ui/streamlit_app.py
──────────────────────────────────────────────────────────────
Streamlit UI for the Company Intelligence Agentic System.
Run: streamlit run ui/streamlit_app.py
──────────────────────────────────────────────────────────────
"""

import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from app.controller import CompanyIntelController, PipelineResult
from config.settings import settings

# ─────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Company Intelligence System",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
# CUSTOM CSS — Dark financial terminal aesthetic
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
}

/* Main background */
.stApp { background-color: #0d1117; }
section[data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #21262d; }

/* Header */
.intel-header {
    background: linear-gradient(135deg, #161b22 0%, #0d1117 100%);
    border: 1px solid #21262d;
    border-radius: 12px;
    padding: 2rem 2.5rem;
    margin-bottom: 1.5rem;
    position: relative;
    overflow: hidden;
}
.intel-header::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, #58a6ff, #3fb950, #f78166);
}
.intel-header h1 {
    font-family: 'IBM Plex Mono', monospace;
    color: #e6edf3;
    font-size: 1.8rem;
    font-weight: 600;
    margin: 0 0 0.3rem 0;
    letter-spacing: -0.5px;
}
.intel-header p {
    color: #8b949e;
    font-size: 0.9rem;
    margin: 0;
    font-family: 'IBM Plex Mono', monospace;
}

/* Metric cards */
.metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 1.5rem; }
.metric-card {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 1.2rem 1.4rem;
    transition: border-color 0.2s;
}
.metric-card:hover { border-color: #388bfd; }
.metric-card .label {
    color: #8b949e;
    font-size: 0.72rem;
    font-family: 'IBM Plex Mono', monospace;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.4rem;
}
.metric-card .value {
    color: #e6edf3;
    font-size: 1.4rem;
    font-weight: 600;
    font-family: 'IBM Plex Mono', monospace;
}
.metric-card .sub {
    color: #8b949e;
    font-size: 0.78rem;
    margin-top: 0.2rem;
    font-family: 'IBM Plex Mono', monospace;
}
.positive { color: #3fb950 !important; }
.negative { color: #f78166 !important; }
.neutral  { color: #d29922 !important; }

/* Section headers */
.section-header {
    font-family: 'IBM Plex Mono', monospace;
    color: #58a6ff;
    font-size: 0.78rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    padding: 0.5rem 0;
    border-bottom: 1px solid #21262d;
    margin-bottom: 1rem;
}

/* Insight / Risk cards */
.insight-card {
    background: #161b22;
    border: 1px solid #21262d;
    border-left: 3px solid #58a6ff;
    border-radius: 8px;
    padding: 0.9rem 1.1rem;
    margin-bottom: 0.6rem;
    color: #c9d1d9;
    font-size: 0.88rem;
    line-height: 1.6;
}
.risk-card {
    background: #161b22;
    border: 1px solid #21262d;
    border-left: 3px solid #f78166;
    border-radius: 8px;
    padding: 0.9rem 1.1rem;
    margin-bottom: 0.6rem;
    color: #c9d1d9;
    font-size: 0.88rem;
    line-height: 1.6;
}

/* Summary box */
.summary-box {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 1.4rem 1.6rem;
    color: #c9d1d9;
    font-size: 0.92rem;
    line-height: 1.75;
}

/* Status badge */
.badge {
    display: inline-block;
    padding: 0.2rem 0.7rem;
    border-radius: 20px;
    font-size: 0.72rem;
    font-family: 'IBM Plex Mono', monospace;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
.badge-positive { background: #0f2d1f; color: #3fb950; border: 1px solid #238636; }
.badge-negative { background: #2d1216; color: #f78166; border: 1px solid #f85149; }
.badge-neutral  { background: #2d2208; color: #d29922; border: 1px solid #9e6a03; }
.badge-high     { background: #0f2d1f; color: #3fb950; border: 1px solid #238636; }
.badge-medium   { background: #2d2208; color: #d29922; border: 1px solid #9e6a03; }
.badge-low      { background: #2d1520; color: #8b949e; border: 1px solid #30363d; }

/* Run metadata bar */
.run-meta {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 0.7rem 1.2rem;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.73rem;
    color: #8b949e;
    display: flex;
    gap: 2rem;
    flex-wrap: wrap;
    margin-bottom: 1.5rem;
}
.run-meta span { color: #58a6ff; }

/* Streamlit overrides */
div[data-testid="stButton"] button {
    background: #238636;
    color: #ffffff;
    border: 1px solid #2ea043;
    border-radius: 8px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.9rem;
    font-weight: 600;
    padding: 0.6rem 2rem;
    width: 100%;
    transition: all 0.2s;
}
div[data-testid="stButton"] button:hover {
    background: #2ea043;
    border-color: #3fb950;
}
div[data-testid="stTextInput"] input {
    background: #161b22;
    border: 1px solid #30363d;
    color: #e6edf3;
    font-family: 'IBM Plex Mono', monospace;
    border-radius: 8px;
}
div[data-testid="stTextInput"] input:focus { border-color: #388bfd; }
div[data-testid="stSelectbox"] select,
div[data-testid="stSelectbox"] > div {
    background: #161b22 !important;
    color: #e6edf3 !important;
    border-color: #30363d !important;
    font-family: 'IBM Plex Mono', monospace;
}
.stAlert { border-radius: 8px; }
div[data-testid="stMarkdownContainer"] h1,
div[data-testid="stMarkdownContainer"] h2,
div[data-testid="stMarkdownContainer"] h3 { color: #e6edf3; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def sentiment_badge(sentiment: str) -> str:
    icons = {"positive": "▲", "negative": "▼", "neutral": "◆"}
    icon = icons.get(sentiment, "◆")
    return f'<span class="badge badge-{sentiment}">{icon} {sentiment.upper()}</span>'

def confidence_badge(confidence: str) -> str:
    stars = {"high": "●●●", "medium": "●●○", "low": "●○○"}
    star = stars.get(confidence, "●○○")
    return f'<span class="badge badge-{confidence}">{star} {confidence.upper()}</span>'

def change_color(pct) -> str:
    if pct is None: return "#8b949e"
    return "#3fb950" if float(pct) >= 0 else "#f78166"

def render_metric(label: str, value: str, sub: str = "", color: str = "") -> str:
    val_style = f'style="color:{color}"' if color else ""
    return f"""
    <div class="metric-card">
        <div class="label">{label}</div>
        <div class="value" {val_style}>{value}</div>
        {'<div class="sub">' + sub + '</div>' if sub else ''}
    </div>"""


# ─────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
    <div style="padding:1rem 0 0.5rem;font-family:'IBM Plex Mono',monospace;">
        <div style="color:#58a6ff;font-size:0.7rem;text-transform:uppercase;
                    letter-spacing:0.1em;margin-bottom:0.8rem">⬡ System Config</div>
    </div>""", unsafe_allow_html=True)

    provider_color = "#3fb950" if settings.has_llm_key else "#f78166"
    mock_color     = "#d29922" if settings.use_mock_data else "#3fb950"

    st.markdown(f"""
    <div style="background:#0d1117;border:1px solid #21262d;border-radius:8px;
                padding:1rem;margin-bottom:1rem;font-family:'IBM Plex Mono',monospace;
                font-size:0.75rem;color:#8b949e;line-height:2">
        <div>Provider &nbsp;<span style="color:{provider_color}">{settings.llm_provider.upper()}</span></div>
        <div>Model &nbsp;&nbsp;&nbsp;<span style="color:#e6edf3">{settings.active_model}</span></div>
        <div>LLM Key &nbsp;<span style="color:{provider_color}">{'✓ SET' if settings.has_llm_key else '✗ MISSING'}</span></div>
        <div>Mock Data <span style="color:{mock_color}">{'ON' if settings.use_mock_data else 'OFF'}</span></div>
    </div>""", unsafe_allow_html=True)

    st.markdown('<div style="color:#8b949e;font-size:0.72rem;font-family:IBM Plex Mono,monospace;margin-bottom:0.4rem">QUICK SELECT</div>', unsafe_allow_html=True)
    quick = st.selectbox("", ["", "Tesla", "Apple Inc", "Microsoft",
                               "NVIDIA", "Amazon", "Google", "Meta",
                               "Netflix", "Adobe"],
                         label_visibility="collapsed")

    st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)
    st.markdown('<div style="color:#8b949e;font-size:0.72rem;font-family:IBM Plex Mono,monospace;margin-bottom:0.4rem">ABOUT</div>', unsafe_allow_html=True)
    st.markdown("""
    <div style="font-size:0.78rem;color:#8b949e;line-height:1.8;font-family:'IBM Plex Sans',sans-serif">
    Multi-agent AI pipeline:<br>
    <span style="color:#58a6ff">① Data Collector</span> → fetches live news + stock data<br>
    <span style="color:#58a6ff">② Analyst</span> → LLM-powered analysis<br>
    <span style="color:#58a6ff">③ Orchestrator</span> → LangGraph StateGraph
    </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# MAIN LAYOUT
# ─────────────────────────────────────────────────────────────

st.markdown("""
<div class="intel-header">
    <h1>🏢 Company Intelligence System</h1>
    <p>Multi-Agent AI · LangGraph · Groq llama-3.3-70b · Live Data</p>
</div>""", unsafe_allow_html=True)

# Input row
col_input, col_btn = st.columns([4, 1])
with col_input:
    company_input = st.text_input(
        "Company Name",
        value=quick if quick else "",
        placeholder="e.g.  Tesla,  Apple Inc,  NVIDIA ...",
        label_visibility="collapsed",
    )
with col_btn:
    run_btn = st.button("▶  Analyze", use_container_width=True)

# ─────────────────────────────────────────────────────────────
# RUN PIPELINE
# ─────────────────────────────────────────────────────────────

if run_btn:
    company = (company_input or "").strip()
    if not company:
        st.warning("⚠ Please enter a company name.")
        st.stop()

    # ── Progress feedback ─────────────────────────────────────
    progress_bar = st.progress(0)
    status_text  = st.empty()

    stages = [
        (0.15, "🔍  Initializing pipeline..."),
        (0.35, "📰  Fetching news data..."),
        (0.55, "📈  Fetching stock data..."),
        (0.75, "🧠  Running LLM analysis (Groq)..."),
        (0.90, "📋  Formatting intelligence report..."),
    ]

    # Animate progress while pipeline runs (non-blocking visual)
    result_holder = st.empty()

    for pct, msg in stages[:2]:
        status_text.markdown(
            f'<div style="color:#8b949e;font-family:IBM Plex Mono,monospace;'
            f'font-size:0.8rem">{msg}</div>', unsafe_allow_html=True)
        progress_bar.progress(pct)
        time.sleep(0.3)

    # ── Actually run ──────────────────────────────────────────
    try:
        ctrl   = CompanyIntelController()
        result: PipelineResult = ctrl.run(company)
    except Exception as e:
        st.error(f"❌ Unexpected error: {e}")
        st.stop()

    # Finish progress animation
    for pct, msg in stages[2:]:
        status_text.markdown(
            f'<div style="color:#8b949e;font-family:IBM Plex Mono,monospace;'
            f'font-size:0.8rem">{msg}</div>', unsafe_allow_html=True)
        progress_bar.progress(pct)
        time.sleep(0.25)

    progress_bar.progress(1.0)
    status_text.empty()

    # ── Store in session for re-display ───────────────────────
    st.session_state["result"] = result


# ─────────────────────────────────────────────────────────────
# DISPLAY RESULT
# ─────────────────────────────────────────────────────────────

if "result" in st.session_state:
    r: PipelineResult = st.session_state["result"]

    if not r.succeeded:
        st.error(f"❌ Pipeline failed: {r.error_message}")
        st.stop()

    # ── Run metadata bar ──────────────────────────────────────
    direction = "▲" if (r.change_pct or 0) >= 0 else "▼"
    chg_col   = "#3fb950" if (r.change_pct or 0) >= 0 else "#f78166"
    st.markdown(f"""
    <div class="run-meta">
        <div>RUN&nbsp;<span>{r.run_id}</span></div>
        <div>TIME&nbsp;<span>{r.execution_time_s}s</span></div>
        <div>SOURCES&nbsp;<span>{r.news_source}/{r.stock_source}</span></div>
        <div>ARTICLES&nbsp;<span>{r.article_count}</span></div>
        <div>EXECUTED&nbsp;<span>{r.executed_at}</span></div>
    </div>""", unsafe_allow_html=True)

    # ── Metric cards ──────────────────────────────────────────
    price_str  = f"${r.current_price:,.2f}" if r.current_price else "N/A"
    change_str = f"{direction} {abs(r.change_pct or 0):.2f}%" if r.change_pct is not None else "N/A"
    st.markdown(f"""
    <div class="metric-grid">
        {render_metric("Ticker", r.ticker or "N/A")}
        {render_metric("Price", price_str, change_str, change_color(r.change_pct))}
        {render_metric("Market Cap", r.market_cap or "N/A")}
        {render_metric("News Articles", str(r.article_count), f"last 14 days")}
    </div>""", unsafe_allow_html=True)

    # ── Sentiment + Confidence row ────────────────────────────
    s_col, c_col, _ = st.columns([1, 1, 4])
    with s_col:
        st.markdown(f"**Sentiment** &nbsp; {sentiment_badge(r.sentiment)}",
                    unsafe_allow_html=True)
    with c_col:
        st.markdown(f"**Confidence** &nbsp; {confidence_badge(r.confidence)}",
                    unsafe_allow_html=True)

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # ── Tabs ──────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📋 Summary", "💡 Insights", "⚠️ Risks", "📄 Full Report"]
    )

    with tab1:
        st.markdown('<div class="section-header">Executive Summary</div>',
                    unsafe_allow_html=True)
        st.markdown(f'<div class="summary-box">{r.summary}</div>',
                    unsafe_allow_html=True)
        if r.error_message:
            st.info(f"ℹ️ Note: {r.error_message}")

    with tab2:
        st.markdown('<div class="section-header">Key Insights</div>',
                    unsafe_allow_html=True)
        for insight in r.key_insights:
            st.markdown(f'<div class="insight-card">💡 {insight}</div>',
                        unsafe_allow_html=True)

    with tab3:
        st.markdown('<div class="section-header">Risk Factors</div>',
                    unsafe_allow_html=True)
        for risk in r.risk_factors:
            st.markdown(f'<div class="risk-card">⚠️ {risk}</div>',
                        unsafe_allow_html=True)

    with tab4:
        st.markdown('<div class="section-header">Full Markdown Report</div>',
                    unsafe_allow_html=True)
        st.markdown(r.final_report)
        st.download_button(
            label="⬇ Download Report (.md)",
            data=r.final_report,
            file_name=f"intel_{r.company.replace(' ','_')}_{r.run_id}.md",
            mime="text/markdown",
        )

else:
    # ── Empty state ───────────────────────────────────────────
    st.markdown("""
    <div style="text-align:center;padding:4rem 2rem;color:#8b949e;">
        <div style="font-size:3rem;margin-bottom:1rem">🏢</div>
        <div style="font-family:'IBM Plex Mono',monospace;font-size:1rem;
                    color:#e6edf3;margin-bottom:0.5rem">
            Company Intelligence System
        </div>
        <div style="font-size:0.85rem;line-height:1.8">
            Enter a company name above and click <strong>Analyze</strong><br>
            to run the full multi-agent intelligence pipeline.
        </div>
        <div style="margin-top:2rem;display:flex;justify-content:center;
                    gap:1.5rem;flex-wrap:wrap">
            <span style="font-family:'IBM Plex Mono',monospace;font-size:0.75rem;
                         background:#161b22;border:1px solid #21262d;padding:0.4rem 1rem;
                         border-radius:20px;color:#58a6ff">Tesla</span>
            <span style="font-family:'IBM Plex Mono',monospace;font-size:0.75rem;
                         background:#161b22;border:1px solid #21262d;padding:0.4rem 1rem;
                         border-radius:20px;color:#58a6ff">Apple Inc</span>
            <span style="font-family:'IBM Plex Mono',monospace;font-size:0.75rem;
                         background:#161b22;border:1px solid #21262d;padding:0.4rem 1rem;
                         border-radius:20px;color:#58a6ff">NVIDIA</span>
            <span style="font-family:'IBM Plex Mono',monospace;font-size:0.75rem;
                         background:#161b22;border:1px solid #21262d;padding:0.4rem 1rem;
                         border-radius:20px;color:#58a6ff">Microsoft</span>
        </div>
    </div>""", unsafe_allow_html=True)
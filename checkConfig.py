"""
check_config.py
────────────────────────────────────────────────
Run this any time things aren't working:
    python check_config.py

It reads your .env and tells you exactly what
is set, what is missing, and what to fix.
────────────────────────────────────────────────
"""
from config.settings import settings

W = "⚠️ "
OK = "✅"
ERR = "❌"

print("\n" + "═" * 52)
print("  .ENV CONFIGURATION VALIDATOR")
print("═" * 52)

# ── LLM Provider ──────────────────────────────
print(f"\n  LLM Provider : {settings.llm_provider.upper()}")
print(f"  Active Model : {settings.active_model}")

if settings.llm_provider == "groq":
    raw_key = settings.groq_api_key
    if not raw_key:
        print(f"  {ERR} GROQ_API_KEY  : NOT SET")
        print(f"       → Add GROQ_API_KEY=gsk_... to your .env")
        print(f"       → Get free key: https://console.groq.com")
    elif "your-groq" in raw_key or raw_key == "your-groq-key-here":
        print(f"  {ERR} GROQ_API_KEY  : STILL A PLACEHOLDER")
        print(f"       → Replace with your real key from console.groq.com")
        print(f"       → It should start with: gsk_")
    else:
        masked = raw_key[:8] + "..." + raw_key[-4:]
        print(f"  {OK} GROQ_API_KEY  : {masked} (set correctly)")

elif settings.llm_provider == "openai":
    raw_key = settings.openai_api_key
    if not raw_key or "your-openai" in raw_key:
        print(f"  {ERR} OPENAI_API_KEY: NOT SET or placeholder")
        print(f"       → Add OPENAI_API_KEY=sk-... to your .env")
    else:
        masked = raw_key[:8] + "..." + raw_key[-4:]
        print(f"  {OK} OPENAI_API_KEY: {masked} (set correctly)")

# ── Mock mode ──────────────────────────────────
print()
if settings.use_mock_data:
    print(f"  {W} USE_MOCK_DATA  : true  ← LLM is BLOCKED")
    print(f"       → Set USE_MOCK_DATA=false to enable LLM calls")
else:
    print(f"  {OK} USE_MOCK_DATA  : false (LLM calls enabled)")

# ── Final verdict ─────────────────────────────
print()
llm_ready = settings.has_llm_key and not settings.use_mock_data
if llm_ready:
    print(f"  ✅ READY — {settings.llm_provider.upper()} LLM will be used")
else:
    print(f"  ❌ NOT READY — rule-based fallback will run")
    print(f"\n  Quick fix checklist:")
    if not settings.has_llm_key:
        if settings.llm_provider == "groq":
            print(f"    1. Go to https://console.groq.com → API Keys → Create")
            print(f"    2. Copy the key (starts with gsk_)")
            print(f"    3. In your .env: GROQ_API_KEY=gsk_xxxxxxxxxxxxx")
        else:
            print(f"    1. Go to https://platform.openai.com/api-keys")
            print(f"    2. In your .env: OPENAI_API_KEY=sk-xxxxxxxxxxxxx")
    if settings.use_mock_data:
        print(f"    {'2' if not settings.has_llm_key else '1'}. In your .env: USE_MOCK_DATA=false")
    print(f"    Then re-run: python test_agents.py")

print("\n" + "═" * 52 + "\n")
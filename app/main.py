"""
app/main.py — CLI entry point
Run: python -m app.main --company "Tesla"
     python -m app.main --company "Apple Inc" --retries 2
"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.controller import CompanyIntelController
from config.settings import settings
from config.logger import logger


def main():
    parser = argparse.ArgumentParser(description="Company Intelligence System")
    parser.add_argument("--company", type=str, default="Apple Inc")
    parser.add_argument("--retries", type=int, default=settings.max_retries)
    args = parser.parse_args()

    for w in settings.validate():
        logger.warning(w)

    ctrl   = CompanyIntelController(max_retries=args.retries)
    result = ctrl.run(company=args.company)

    print("\n" + "═" * 62)
    print(result.final_report)
    print("═" * 62)
    print(f"\n  Run ID     : {result.run_id}")
    print(f"  Status     : {result.status}")
    print(f"  Time       : {result.execution_time_s}s")
    print(f"  Attempts   : {result.attempts}")
    print(f"  Sentiment  : {result.sentiment}")
    print(f"  Confidence : {result.confidence}")


if __name__ == "__main__":
    main()
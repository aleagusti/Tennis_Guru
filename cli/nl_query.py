# =================================
# Ensure project root is on PYTHONPATH
# =================================
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.engine import TennisGuruEngine, format_for_cli

def main():
    engine = TennisGuruEngine()

    while True:
        q = input("Ask Tennis Guru (or type 'exit'): ").strip()
        if not q:
            continue
        if q.lower() in {"exit", "quit", "q"}:
            print("Bye! 🎾")
            break

        res = engine.process(q)

        # Handle engine-level errors
        if getattr(res, "error", None):
            print("\n❌ Error:\n")
            print(res.error)
            continue

        if res.cached:
            print("\n⚡ Cached result used.")

        if res.explanation:
            print("\n--- Explanation ---\n")
            print(res.explanation)

        print("\n--- Results ---\n")

        # Optional total execution time display
        if getattr(res, "total_time", None) is not None:
            print(f"\n⏱ Total time: {res.total_time:.3f}s")

        print(format_for_cli(res))

if __name__ == "__main__":
    main()
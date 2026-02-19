from __future__ import annotations

import os
import json
import time
from datetime import datetime
from pathlib import Path

# Adjust path to import from src
import sys
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.engine import TennisGuruEngine

STRESS_FILE = PROJECT_ROOT / "tests" / "stress_tests.txt"
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "query_benchmark.json"


def load_questions():
    """
    Parses structured stress test file.
    Expected format:

    [L2][temporal-rank]
    How many matches did Federer win while ranked number 1?

    Blank lines and lines starting with # are ignored.
    """
    questions = []
    current_meta = {}

    with open(STRESS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            # Metadata line
            if line.startswith("["):
                # Example: [L2][temporal-rank]
                parts = line.replace("]", "").split("[")
                parts = [p for p in parts if p]
                current_meta = {
                    "level": parts[0] if len(parts) > 0 else None,
                    "tag": parts[1] if len(parts) > 1 else None,
                }
                continue

            # Question line
            questions.append({
                "question": line,
                "level": current_meta.get("level"),
                "tag": current_meta.get("tag")
            })

    return questions


def benchmark():
    results = []
    questions = load_questions()

    print(f"Running benchmark on {len(questions)} questions...\n")

    engine = TennisGuruEngine()

    for item in questions:
        q = item["question"]
        level = item.get("level")
        tag = item.get("tag")

        print(f"→ [{level}][{tag}] {q}")

        entry = {
            "question": q,
            "level": level,
            "tag": tag,
            "llm_generation_time": None,
            "sql_execution_time": None,
            "simplification_triggered": False,
            "timeout": False,
            "error": None,
            "needs_clarification": False,
            "generated_sql": None,   # raw SQL from LLM
            "final_sql": None,       # SQL after guard + transformer
            "result_sample": None,
            "timestamp": datetime.utcnow().isoformat()
        }

        try:
            start_total = time.time()
            res = engine.process(q)
            total_time = round(time.time() - start_total, 4)

            # Store both raw LLM SQL and final executed SQL
            entry["generated_sql"] = getattr(res, "generated_sql", None)
            entry["final_sql"] = res.sql

            entry["needs_clarification"] = res.needs_clarification
            entry["error"] = res.error

            # Timing metrics
            entry["llm_generation_time"] = getattr(res, "llm_generation_time", None)
            entry["sql_execution_time"] = total_time

            if res.results:
                entry["result_sample"] = res.results[:3]

        except Exception as e:
            entry["error"] = str(e)

        results.append(entry)

    # Persist results
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\nBenchmark complete.")
    print(f"Results saved to {LOG_FILE}")


if __name__ == "__main__":
    benchmark()

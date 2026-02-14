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

from src.core.nl_query import (
    generate_sql_from_question,
    run_query,
    is_query_too_complex,
    is_question_ambiguous,
)

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
            "generated_sql": None,
            "result_sample": None,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Handle ambiguous questions (no SQL should be generated)
        if is_question_ambiguous(q):
            entry["needs_clarification"] = True
            results.append(entry)
            print("  ↳ Marked as needs_clarification (no SQL executed)")
            continue

        try:
            # Measure SQL generation time
            start_llm = time.time()
            sql, _ = generate_sql_from_question(q)
            entry["llm_generation_time"] = round(time.time() - start_llm, 4)
            entry["generated_sql"] = sql

            # Detect complexity
            if is_query_too_complex(sql):
                entry["simplification_triggered"] = True

            # Measure SQL execution time
            start_sql = time.time()
            try:
                rows = run_query(sql)
                if rows:
                    entry["result_sample"] = rows[:3]
            except Exception as e:
                if "interrupted" in str(e).lower():
                    entry["timeout"] = True
                else:
                    entry["error"] = str(e)
            entry["sql_execution_time"] = round(time.time() - start_sql, 4)

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

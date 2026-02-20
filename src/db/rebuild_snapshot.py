import sys
from pathlib import Path

# Ensure project root is in sys.path when running as a script
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import sqlite3
from src.setup.materialized_views import build_match_rank_snapshot

DB_PATH = PROJECT_ROOT / "data" / "guru.db"

def rebuild():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DROP TABLE IF EXISTS match_rank_snapshot;")
    conn.commit()
    conn.close()

    build_match_rank_snapshot(str(DB_PATH))
    print("Snapshot rebuilt successfully.")

if __name__ == "__main__":
    rebuild()
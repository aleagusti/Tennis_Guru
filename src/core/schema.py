import sqlite3
import re
from pathlib import Path
from functools import lru_cache

DB_PATH = Path("data/guru.db")

SCHEMA_DESCRIPTION = """
Tables:

players(
    player_id INTEGER,
    first_name TEXT,
    last_name TEXT,
    gender TEXT,
    hand TEXT,
    dob DATE,
    country TEXT,
    height INTEGER
)

rankings(
    player_id INTEGER,
    ranking_date DATE,
    rank INTEGER,
    points INTEGER,
    gender TEXT
)

matches(
    match_id INTEGER,
    tour TEXT,
    tourney_id TEXT,
    tourney_name TEXT,
    surface TEXT,
    tourney_level TEXT,
    match_date DATE,
    round TEXT,
    best_of INTEGER,
    winner_id INTEGER,
    loser_id INTEGER,
    winner_rank INTEGER,
    loser_rank INTEGER,
    w_ace INTEGER,
    l_ace INTEGER,
    score TEXT
)
Note:
Match statistics are split by side:
- Columns starting with "w_" refer to the winner.
- Columns starting with "l_" refer to the loser.
To compute player-level totals, use CASE on winner_id and loser_id.
"""

# -------------------------------------------------
# Schema loading (cached)
# -------------------------------------------------

@lru_cache(maxsize=1)
def get_db_schema(db_path: Path = DB_PATH) -> dict[str, set[str]]:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    schema: dict[str, set[str]] = {}
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cur.fetchall()]

    for table in tables:
        cur.execute(f"PRAGMA table_info({table});")
        columns = {row[1] for row in cur.fetchall()}
        schema[table] = columns

    conn.close()
    return schema



# -------------------------------------------------
# Identifier extraction (safe minimal version)
# -------------------------------------------------

def extract_identifiers(sql: str) -> set[str]:
    """
    Extract only column names referenced as alias.column.
    This avoids false positives from SQL keywords, functions,
    aliases, table names, etc.
    """
    # Remove string literals
    sql = re.sub(r"'[^']*'", "", sql)
    sql = re.sub(r'"[^"]*"', "", sql)

    # Extract only alias.column patterns
    matches = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\.(\w+)\b", sql)

    return set(matches)


# -------------------------------------------------
# Schema validation (column-level only)
# -------------------------------------------------

def validate_schema(sql: str, db_path: Path = DB_PATH) -> None:
    schema = get_db_schema(db_path)

    identifiers = extract_identifiers(sql)

    # Build set of real DB columns
    all_columns = set()
    for cols in schema.values():
        all_columns.update(cols)

    # Only validate actual column names
    unknown = [
        col for col in identifiers
        if col not in all_columns
    ]

    if unknown:
        raise ValueError(f"Unknown columns detected: {unknown}")
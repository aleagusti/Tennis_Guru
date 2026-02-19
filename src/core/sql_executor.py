import re
import time
import sqlite3
from pathlib import Path
from .schema import DB_PATH, validate_schema

def validate_sql(sql: str) -> None:
    sql_clean = sql.strip().lower()
    if not sql_clean.startswith("select"):
        raise ValueError("Only SELECT queries are allowed.")

    forbidden = ["drop", "delete", "update", "insert", "alter"]
    for word in forbidden:
        if re.search(rf"\b{word}\b", sql_clean):
            raise ValueError(f"Forbidden keyword detected: {word}")

def run_query(sql: str, timeout_seconds: int = 30, db_path: Path = DB_PATH):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    start_time = time.time()

    def progress_handler():
        if time.time() - start_time > timeout_seconds:
            return 1
        return 0

    conn.set_progress_handler(progress_handler, 100000)
    try:
        cur.execute(sql)
        results = cur.fetchall()
    finally:
        conn.set_progress_handler(None, 0)
        conn.close()

    return results

def execute_sql(sql: str, timeout_seconds: int = 30, db_path: Path = DB_PATH):
    validate_sql(sql)
    validate_schema(sql, db_path=db_path)
    return run_query(sql, timeout_seconds=timeout_seconds, db_path=db_path)
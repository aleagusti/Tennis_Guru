import sqlite3
from pathlib import Path

DB_PATH = Path("data/guru.db")
SCHEMA_PATH = Path("src/db/schema.sql")


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)

    with open(SCHEMA_PATH, "r") as f:
        schema_sql = f.read()
        conn.executescript(schema_sql)

    conn.close()
    print("Database initialized successfully.")


if __name__ == "__main__":
    init_db()
import sqlite3
from pathlib import Path
import re
import os
import time
from openai import OpenAI
from dotenv import load_dotenv

from openai import RateLimitError, AuthenticationError, APIError


load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")
print("Loaded API key:", os.getenv("OPENAI_API_KEY") is not None)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# NOTE:
# This module is intentionally minimal.
# It assumes you will plug in an LLM call inside generate_sql_from_question().
# For now, it is structured for easy integration.


DB_PATH = Path("data/guru.db")

# =========================
# AMBIGUOUS QUESTION DETECTION
# =========================

AMBIGUOUS_KEYWORDS = {
    "best player",
    "most impressive",
    "strongest era",
    "most dominant",
    "greatest",
    "strongest generation",
    "best era",
    "biggest upset",
    "most impressive career",
    "who was better",
    "who was more dominant"
}


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
    -- Note: Finals are stored as 'F', not 'Final'
    best_of INTEGER,
    winner_id INTEGER,
    loser_id INTEGER,
    winner_rank INTEGER,
    loser_rank INTEGER,
    score TEXT
)
"""

# =========================
# SCHEMA INTROSPECTION
# =========================

def get_db_schema() -> dict:
    """
    Dynamically introspect SQLite schema and return
    {table_name: set(columns)}.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    schema = {}
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cur.fetchall()]

    for table in tables:
        cur.execute(f"PRAGMA table_info({table});")
        columns = {row[1] for row in cur.fetchall()}
        schema[table] = columns

    conn.close()
    return schema


def extract_identifiers(sql: str) -> set:
    """
    Extract potential column identifiers from SQL.
    This is heuristic-based and not a full SQL parser.
    """
    tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", sql)
    keywords = {
        "select", "from", "where", "and", "or", "not", "in",
        "exists", "join", "on", "group", "by", "order", "limit",
        "as", "desc", "asc", "count", "distinct"
    }
    return {t for t in tokens if t.lower() not in keywords}


def validate_schema(sql: str) -> None:
    """
    Ensure referenced columns actually exist in DB schema.
    Raises ValueError if unknown column detected.
    """
    schema = get_db_schema()
    identifiers = extract_identifiers(sql)

    # Flatten all known columns
    all_columns = set()
    for cols in schema.values():
        all_columns.update(cols)

    unknown = []
    for identifier in identifiers:
        # Ignore table names
        if identifier in schema:
            continue
        if identifier not in all_columns:
            unknown.append(identifier)

    if unknown:
        raise ValueError(f"Unknown columns detected: {unknown}")


def is_question_ambiguous(question: str) -> bool:
    q = question.strip().lower()
    return any(k in q for k in AMBIGUOUS_KEYWORDS)


def generate_sql_from_question(question: str) -> tuple[str, str]:
    prompt = f"""
You are an expert SQLite query generator.

Convert the following natural language question into a valid SQLite SELECT query.

Important rules:
- Finals are stored as round = 'F'.
- If the question asks for "finals played" / "finales jugó" / "reached finals", interpret it as round = 'F' AND (winner_id = player OR loser_id = player).
- If the question asks for "finals won" / "finales ganó" / "won finals", interpret it as round = 'F' AND winner_id = player.
- When a question refers to ranking "at the time", you MUST use the latest ranking_date <= match_date.
- Do NOT join rankings directly on ranking_date = match_date.
- Instead, use a correlated subquery ordered by ranking_date DESC with LIMIT 1.
- Only apply ranking_date <= match_date logic if the question explicitly refers to ranking "at the time" (e.g., "at that moment", "en ese momento").
- If the question is about historical peak rank (e.g., "was number 1"), do NOT introduce match_date constraints or temporal ranking logic.
- IMPORTANT: Prefer using matches.winner_rank and matches.loser_rank for opponent rank "at the time" questions whenever possible (this is faster and already represents rank at match time).
- For "lost against Top N at the time" where the player is the loser, filter winner_rank <= N.
- For "won against Top N at the time" where the player is the winner, filter loser_rank <= N.
- If the question refers to opponent ranking, use loser_id for winner queries.
- The rankings.gender column uses ONLY 'ATP' or 'WTA' (never 'M'/'F').
- Use rankings.gender = 'ATP' for men's questions and rankings.gender = 'WTA' for women's questions.
- SQLite date arithmetic: do NOT use INTERVAL. Use date(dob, '+25 years') and compare match_date to that.
- Only generate a SELECT statement.
- Do NOT include markdown code fences.
- Do NOT include explanations inside the SQL.
- The user question may be in any language.
- Interpret it correctly before generating SQL.
- Grand Slam tournaments are stored as tourney_level = 'G'.
- Winning a Grand Slam means tourney_level = 'G' AND round = 'F' AND winner_id equals the player.
- Do NOT treat participation in a Grand Slam as winning.

Database schema:
{SCHEMA_DESCRIPTION}

Question:
{question}
"""

    response = client.responses.create(
        model="gpt-4o-mini",
        input=[
            {
                "role": "system",
                "content": "You generate safe SQLite SELECT queries."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0
    )

    # Extract text from Responses API structure
    sql = response.output[0].content[0].text.strip()

    # Remove markdown code fences if present
    if sql.startswith("```"):
        sql = re.sub(r"^```.*?\n", "", sql)
        sql = re.sub(r"```$", "", sql).strip()

    explanation = "SQL generated from natural language question."

    return sql, explanation



def validate_sql(sql: str) -> None:
    """
    Safety check: allow only SELECT queries.
    """

    sql_clean = sql.strip().lower()

    if not sql_clean.startswith("select"):
        raise ValueError("Only SELECT queries are allowed.")

    forbidden = ["drop", "delete", "update", "insert", "alter"]
    for word in forbidden:
        if re.search(rf"\b{word}\b", sql_clean):
            raise ValueError(f"Forbidden keyword detected: {word}")


# Simple query complexity detector
def is_query_too_complex(sql: str) -> bool:
    """
    Heuristic detector for potentially expensive queries.
    Flags:
    - Multiple EXISTS clauses
    - Nested SELECT inside SELECT
    - OR inside correlated subqueries
    """
    sql_lower = sql.lower()

    # Too many EXISTS
    if sql_lower.count("exists") > 1:
        return True

    # Deep nesting
    if sql_lower.count("select") > 4:
        return True

    # Correlated subqueries with OR
    if re.search(r"\(\s*select.*?or.*?\)", sql_lower, re.DOTALL):
        return True

    # Excessive NOT IN
    if sql_lower.count("not in") > 1:
        return True

    return False


# Automatic SQL simplification using LLM
def simplify_sql(original_sql: str) -> str:
    """
    Ask the model to rewrite a complex query into a simpler, more efficient form.
    """
    prompt = f"""
The following SQLite query is valid but potentially too complex or inefficient.
Rewrite it into a simpler and more efficient SELECT query.

STRICT REQUIREMENTS:
- You MUST preserve the exact logical meaning of the original query.
- Do NOT broaden or narrow the result set.
- Do NOT introduce new exclusion logic.
- If the original query excludes only winners, you must NOT exclude losers.
- Do NOT exclude players simply for participating in tournaments.
- Preserve critical filters such as round = 'F' and tourney_level = 'G'.
- If the original logic excludes only m.winner_id, the simplified query must also exclude only m.winner_id.
- NEVER replace NOT EXISTS logic with LEFT JOIN ... IS NULL when an OR condition is involved.
- NEVER use LEFT JOIN with OR inside the join condition.
- Prefer JOIN + NOT IN (winner_id only) instead of nested EXISTS when possible.
- Avoid correlated subqueries if possible.
- Do NOT introduce new temporal constraints (match_date/ranking_date logic) unless they already exist in the original query.
- Only return a valid SELECT statement.
- Do NOT include explanations.

Original query:
{original_sql}
"""

    response = client.responses.create(
        model="gpt-4o-mini",
        input=[
            {"role": "system", "content": "You optimize SQLite SELECT queries."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    simplified = response.output[0].content[0].text.strip()

    if simplified.startswith("```"):
        simplified = re.sub(r"^```.*?\n", "", simplified)
        simplified = re.sub(r"```$", "", simplified).strip()

    return simplified


def run_query(sql: str, timeout_seconds: int = 30):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    start_time = time.time()

    # Abort long-running queries
    def progress_handler():
        if time.time() - start_time > timeout_seconds:
            return 1  # non-zero aborts query
        return 0

    conn.set_progress_handler(progress_handler, 100000)

    try:
        cur.execute(sql)
        results = cur.fetchall()
    finally:
        conn.set_progress_handler(None, 0)
        conn.close()

    return results


def ask(question: str):
    # Step 0: Ask for clarification on subjective/ambiguous questions
    if is_question_ambiguous(question):
        print("\n⚠️ This question is ambiguous and needs a definition of the metric.")
        print("Choose one metric so I can answer reliably:")
        print("1) Peak rank (best rank achieved)")
        print("2) Weeks at #1 / Top 10")
        print("3) Titles (non-Grand Slam, Grand Slam, or all)")
        print("4) Win percentage (overall or vs Top N)")
        print("\nReply with the option number and any constraints (e.g., ATP only, since 1990).")
        return

    # Step 1: Generate SQL via OpenAI
    try:
        sql, explanation = generate_sql_from_question(question)
    except AuthenticationError:
        print("\n❌ OpenAI authentication failed. Check your API key.")
        return
    except RateLimitError:
        print("\n❌ OpenAI quota exceeded. Check billing or usage limits.")
        return
    except APIError as e:
        print("\n❌ OpenAI API error occurred.")
        print(str(e))
        return
    except Exception as e:
        print("\n❌ Unexpected error during SQL generation.")
        print(str(e))
        return

    print("\n--- Generated SQL ---\n")
    print(sql)

    print("\n--- Explanation ---\n")
    print(explanation)

    # Step 2: Validate SQL safety
    try:
        validate_sql(sql)
        # Step 2.2: Validate schema consistency
        try:
            validate_schema(sql)
        except ValueError as e:
            print("\n❌ Schema validation failed.")
            print(str(e))
            return
    except ValueError as e:
        print("\n❌ SQL validation failed.")
        print(str(e))
        return

    # Step 2.5: Detect complex queries
    if is_query_too_complex(sql):
        print("\n⚠️ Query deemed too complex. Attempting automatic simplification...")
        try:
            simplified_sql = simplify_sql(sql)
            print("\n--- Simplified SQL ---\n")
            print(simplified_sql)
            validate_sql(simplified_sql)
            sql = simplified_sql
        except Exception as e:
            print("\n❌ Failed to simplify query.")
            print(str(e))
            return

    # Step 3: Execute query against SQLite
    try:
        results = run_query(sql)
    except sqlite3.Error as e:
        msg = str(e)
        if "interrupted" in msg.lower():
            print("\n⏱️ Query timed out (took too long). Try simplifying the question or adding filters.")
        else:
            print("\n❌ Database execution error.")
            print(msg)
        return
    except Exception as e:
        print("\n❌ Unexpected database error.")
        print(str(e))
        return

    print("\n--- Results ---\n")

    if not results:
        print("No results found.")
        return results

    # If single numeric result, generate natural language answer
    if len(results) == 1 and len(results[0]) == 1 and isinstance(results[0][0], (int, float)):
        numeric_result = results[0][0]

        try:
            answer_prompt = f"""
User question:
{question}

Numeric result from database:
{numeric_result}

Generate a short, natural language answer to the user question.
Be concise.
Do not mention SQL.
"""

            response = client.responses.create(
                model="gpt-4o-mini",
                input=[
                    {"role": "system", "content": "You generate concise natural language answers from database results."},
                    {"role": "user", "content": answer_prompt}
                ],
                temperature=0
            )

            final_answer = response.output[0].content[0].text.strip()
            print(final_answer)

        except Exception:
            # Fallback if LLM fails
            print(f"Result: {numeric_result}")

        return results

    # If name pairs
    if len(results[0]) == 2 and all(isinstance(col, str) for col in results[0]):
        try:
            names = ", ".join(f"{row[0]} {row[1]}" for row in results)

            answer_prompt = f"""
User question:
{question}

Database result (names):
{names}

Generate a short, natural language answer to the user question.
Be concise.
Do not mention SQL.
"""

            response = client.responses.create(
                model="gpt-4o-mini",
                input=[
                    {"role": "system", "content": "You generate concise natural language answers from database results."},
                    {"role": "user", "content": answer_prompt}
                ],
                temperature=0
            )

            final_answer = response.output[0].content[0].text.strip()
            print(final_answer)

        except Exception:
            for row in results:
                print(f"{row[0]} {row[1]}")

        return results

    # Fallback for generic tables
    for row in results:
        print(" | ".join(str(col) for col in row))

    return results


if __name__ == "__main__":
    user_question = input("Ask Tennis Guru: ")
    ask(user_question)

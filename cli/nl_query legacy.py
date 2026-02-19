import sqlite3
from pathlib import Path
import re
import os
import time
from openai import OpenAI
from dotenv import load_dotenv

from openai import RateLimitError, AuthenticationError, APIError


# =========================
# High-level orchestration engine
# =========================
class TennisGuruEngine:
    """
    High-level orchestration layer.
    Central entry point for the full NL → SQL → Validation → Execution pipeline.
    """

    def __init__(self):
        # Future refactor: inject cache/context instead of using globals
        pass

    def process(self, question: str):
        return _ask_impl(question)


load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")
print("Loaded API key:", os.getenv("OPENAI_API_KEY") is not None)


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# =========================
# VERSIONING
# =========================
# Every structural modification to this file must bump VERSION.
# Follow semantic versioning:
# MAJOR: breaking architecture changes
# MINOR: new features (e.g., validation layer, benchmark hooks)
# PATCH: bug fixes or small prompt adjustments
VERSION = "0.3.5"

"""
Changelog:
0.1.0
- Added schema introspection
- Added SQL safety validation (SELECT-only)
- Added complexity detector
- Added automatic simplification
- Added ambiguity detection
- Added timeout protection

0.2.0
- Added simple in-memory query cache (same-process)

0.2.1
- Added benchmark hooks (needs_clarification / logging compatibility)

0.2.2
- Fixed schema validation false-positives for double-quoted literals
- Added interactive REPL loop so multiple questions can be asked without re-running the script
- Cache results for numeric + name outputs (not only the generic-table fallback)

0.2.3
- Improved NL→SQL rules for player name resolution (surname vs full name)
- Clarified "titles / torneos / campeonatos" mapping to finals won (round='F') unless a category is specified

0.3.0
- Introduced deterministic intent classification layer (classify_intent)
- Replaced sequential handler checks with semantic intent router
- Foundation for scalable hybrid architecture (deterministic + LLM routing)

0.3.1
- Context-aware tournament follow-up for same_tournament_multi_defeat intent
- Follow-up "En que torneo..." now reuses last deterministic core query instead of listing all tournaments won

0.3.2
- Enforced case-insensitive comparisons for categorical filters (e.g., surface, tourney_name)
- Prevented failures due to lowercase literals like 'clay' vs stored values like 'Clay'

0.3.3
- Added domain-scope ambiguity detection for "record / most wins" type questions
- System now requests clarification when tournament scope (ATP/WTA/Grand Slam/etc.) is not specified

0.3.4
- Added semantic SQL validation layer
- Prevented accidental round <> 'F' injection
- Prevented unintended round filters in surface win/loss queries
- Added automatic regeneration with stricter rules when semantic validation fails

0.3.5
- Fixed broken generate_sql_from_question implementation (was returning None)
- Removed accidental LLM call inside validate_semantics
- Fixed indentation error causing runtime crash
- Restored proper SQL generation + unpacking behavior
"""

# =========================
# SIMPLE QUERY CACHE
# =========================
# In-memory cache to avoid regenerating SQL and re-running
# identical questions within the same process.
# Key: normalized question string
# Value: dict with sql + results
QUERY_CACHE = {}

# =========================
# SIMPLE CONVERSATION MEMORY
# =========================
# Stores last detected entities and last SQL result context
LAST_CONTEXT = {
    "last_player_names": None,      # e.g., [("David","Nalbandian")]
    "last_intent": None,
    "last_sql": None
}

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

# =========================
# RECORD / SCOPE AMBIGUITY DETECTION (v0.3.3)
# =========================

RECORD_KEYWORDS = {
    "record",
    "récord",
    "most wins",
    "most matches",
    "most victories",
    "all time leader",
    "all-time leader",
    "record of most",
    "record de mas",
    "record de más",
    "mas partidos ganados",
    "más partidos ganados"
}

SCOPE_KEYWORDS = {
    "grand slam",
    "masters",
    "masters 1000",
    "atp",
    "wta",
    "challenger",
    "futures",
    "roland garros",
    "wimbledon",
    "us open",
    "australian open"
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
    Extract column names used in SQL in a safer way.
    Only validates identifiers that appear as table_alias.column_name
    to avoid false positives with aliases and SQL keywords.
    """

    # Remove string literals
    sql_no_strings = re.sub(r"'[^']*'", "", sql)
    sql_no_strings = re.sub(r'"[^"]*"', "", sql_no_strings)

    # Extract alias.column patterns only
    matches = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\.(\w+)\b", sql_no_strings)

    return set(matches)


def validate_schema(sql: str) -> None:
    """
    Ensure referenced columns actually exist in DB schema.
    Validates only alias.column references.
    """
    schema = get_db_schema()
    identifiers = extract_identifiers(sql)

    # Flatten all known columns
    all_columns = set()
    for cols in schema.values():
        all_columns.update(cols)

    unknown = [col for col in identifiers if col not in all_columns]

    if unknown:
        raise ValueError(f"Unknown columns detected: {unknown}")


def is_question_ambiguous(question: str) -> bool:
    q = question.strip().lower()

    # Subjective metric ambiguity (existing logic)
    if any(k in q for k in AMBIGUOUS_KEYWORDS):
        return True

    # Record / scope ambiguity (new logic)
    if any(k in q for k in RECORD_KEYWORDS):
        # If no tournament/category scope is specified, request clarification
        if not any(s in q for s in SCOPE_KEYWORDS):
            return True

    return False


# =========================
# INTENT CLASSIFICATION LAYER (v0.3.0 groundwork)
# =========================

def classify_intent(question: str) -> str | None:
    """
    Lightweight deterministic intent classifier.
    Returns an intent string or None.
    """

    q = question.lower()

    # Same tournament multi-opponent defeat
    if (
        any(p in q for p in ["le gano a", "le ganó a", "derroto a", "derrotó a", "beat", "defeated"])
        and ("mismo torneo" in q or "same tournament" in q)
    ):
        return "same_tournament_multi_defeat"

    # Ranking at specific final (tournament + year)
    if (
        ("final" in q or "final de" in q)
        and re.search(r"\b(19|20)\d{2}\b", question)
        and any(t in q for t in ["wimbledon", "roland garros", "us open", "australian open"])
    ):
        return "ranking_at_final"

    return None


# =========================
# Deterministic multi-opponent same tournament defeat handler
# =========================
def build_same_tournament_multi_defeat_query(question: str) -> str | None:
    """
    Deterministic handler for questions like:
    'Who beat Federer, Nadal and Djokovic in the same tournament?'
    Uses robust proper-name extraction instead of scanning the entire DB
    to avoid substring collisions (e.g., Spanish "le").
    """

    q_lower = question.lower()

    trigger_phrases = [
        "le gano a",
        "le ganó a",
        "derroto a",
        "derrotó a",
        "beat",
        "defeated"
    ]

    if not any(p in q_lower for p in trigger_phrases):
        return None

    if "mismo torneo" not in q_lower and "same tournament" not in q_lower:
        return None

    # Extract candidate full names using capitalized word sequences
    # Example: "Roger Federer", "Rafael Nadal", "Novak Djokovic"
    name_pattern = r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b"
    candidates = re.findall(name_pattern, question)

    if not candidates:
        return None

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    detected_players = []

    for full_name in candidates:
        parts = full_name.strip().split()
        if len(parts) < 2:
            continue

        first = parts[0]
        last = parts[-1]

        # Verify this exact player exists in DB
        cur.execute(
            """
            SELECT player_id
            FROM players
            WHERE lower(first_name) = lower(?)
              AND lower(last_name) = lower(?)
            """,
            (first, last)
        )

        row = cur.fetchone()
        if row:
            detected_players.append((first, last))

    conn.close()

    # Need at least 3 distinct valid players
    detected_players = list(dict.fromkeys(detected_players))  # dedupe while preserving order

    if len(detected_players) < 3:
        return None

    # Use first three valid detected players
    full_names = detected_players[:3]

    # Build UNION subquery for the three opponents
    opponent_subqueries = []
    for first, last in full_names:
        opponent_subqueries.append(f"""
        SELECT player_id FROM players
        WHERE lower(first_name)=lower('{first}')
          AND lower(last_name)=lower('{last}')
        """)

    union_block = "\nUNION\n".join(opponent_subqueries)

    sql = f"""
SELECT DISTINCT p.first_name, p.last_name
FROM matches m
JOIN players p ON p.player_id = m.winner_id
WHERE m.loser_id IN (
{union_block}
)
GROUP BY m.winner_id, m.tourney_id
HAVING COUNT(DISTINCT m.loser_id) = 3;
""".strip()

    return sql


# =========================
# Deterministic ranking-at-final (tournament + year) handler
# =========================
def build_final_ranking_query(question: str) -> str | None:
    """
    Deterministic handler for questions like:
    'What ranking did Federer and Nadal have in the Wimbledon 2008 final?'
    """

    q_lower = question.lower()

    if "final" not in q_lower and "final de" not in q_lower:
        return None

    # Extract 4-digit year
    year_match = re.search(r"\b(19|20)\d{2}\b", question)
    if not year_match:
        return None

    year = year_match.group(0)

    # Extract tournament name (simple heuristic)
    tourney_pattern = r"(Wimbledon|Roland Garros|US Open|Australian Open)"
    tourney_match = re.search(tourney_pattern, question, re.IGNORECASE)

    if not tourney_match:
        return None

    tourney_name = tourney_match.group(0)

    # Extract player full names
    name_pattern = r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b"
    players = re.findall(name_pattern, question)

    if len(players) < 2:
        return None

    first_player = players[0].split()
    second_player = players[1].split()

    sql = f"""
SELECT
    (
        SELECT r.rank
        FROM rankings r
        WHERE r.player_id = (
            SELECT player_id FROM players
            WHERE lower(first_name)=lower('{first_player[0]}')
              AND lower(last_name)=lower('{first_player[-1]}')
        )
        AND r.ranking_date <= m.match_date
        ORDER BY r.ranking_date DESC
        LIMIT 1
    ) AS player1_rank,

    (
        SELECT r.rank
        FROM rankings r
        WHERE r.player_id = (
            SELECT player_id FROM players
            WHERE lower(first_name)=lower('{second_player[0]}')
              AND lower(last_name)=lower('{second_player[-1]}')
        )
        AND r.ranking_date <= m.match_date
        ORDER BY r.ranking_date DESC
        LIMIT 1
    ) AS player2_rank

FROM matches m
WHERE m.tourney_name = '{tourney_name}'
  AND m.round = 'F'
  AND strftime('%Y', m.match_date) = '{year}'
LIMIT 1;
""".strip()

    return sql


def generate_sql_from_question(question: str, extra_rules: str = "") -> tuple[str, str]:
    prompt = f"""
You are an expert SQLite query generator.

Convert the following natural language question into a valid SQLite SELECT query.

Important rules:
- Finals are stored as round = 'F'.
- If the question asks for "finals played" interpret as round = 'F' AND (winner_id = player OR loser_id = player).
- If the question asks for "finals won" interpret as round = 'F' AND winner_id = player.
- When a question refers to ranking "at the time", use latest ranking_date <= match_date.
- Prefer matches.winner_rank / matches.loser_rank for opponent rank at match time.
- Only generate a SELECT statement.
- Do NOT include markdown fences.
- Do NOT include explanations inside SQL.

- STRING FILTERS:
  All categorical TEXT comparisons MUST be case-insensitive:
      lower(column) = lower('Value')

- PLAYER NAME RESOLUTION:
  If full name (2+ tokens) → match first_name AND last_name.
  If single token → assume last_name.
  Always resolve via subquery on players.

Database schema:
{SCHEMA_DESCRIPTION}

Extra rules (if any):
{extra_rules}

Question:
{question}
"""
    response = client.responses.create(
        model="gpt-4o-mini",
        input=[
            {"role": "system", "content": "You generate safe SQLite SELECT queries."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    sql = response.output[0].content[0].text.strip()

    # Remove markdown fences if present
    if sql.startswith("```"):
        sql = re.sub(r"^```.*?\n", "", sql)
        sql = re.sub(r"```$", "", sql).strip()

    explanation = "SQL generated from natural language question."

    return sql, explanation

# =========================
# SEMANTIC GUARD (HP1 - Phase 2 extraction)
# =========================
class SemanticGuard:
    """
    Encapsulates semantic validation rules.
    Centralized location for domain-specific SQL guardrails.
    """

    @staticmethod
    def _question_explicitly_excludes_finals(question: str) -> bool:
        q = question.strip().lower()
        triggers = [
            "excluding finals",
            "exclude finals",
            "without finals",
            "sin finales",
            "excluyendo finales",
            "no finales",
        ]
        return any(t in q for t in triggers)

    @staticmethod
    def _question_mentions_finals_or_titles(question: str) -> bool:
        q = question.strip().lower()
        triggers = [
            "final", "finales", "final de",
            "title", "titles",
            "título", "títulos",
            "torneo", "torneos",
            "campeonato", "campeonatos",
            "grand slam", "masters 1000",
        ]
        return any(t in q for t in triggers)

    @staticmethod
    def _question_is_surface_wins_losses(question: str) -> bool:
        q = question.strip().lower()
        surface_terms = ["clay", "tierra", "tierra batida", "grass", "cesped", "césped", "hard", "cemento"]
        verb_terms = ["won", "wins", "lost", "losses", "played", "partidos", "gan", "perd", "jug"]
        return any(s in q for s in surface_terms) and any(v in q for v in verb_terms)

    @classmethod
    def validate(cls, question: str, sql: str) -> None:
        q = question.strip().lower()
        sql_l = sql.strip().lower()

        if "round <> 'f'" in sql_l or "round != 'f'" in sql_l:
            if not cls._question_explicitly_excludes_finals(question):
                raise ValueError(
                    "Semantic validation failed: query excludes finals (round <> 'F') but the question did not ask to exclude finals."
                )

        if cls._question_is_surface_wins_losses(question):
            if " round " in f" {sql_l} ":
                raise ValueError(
                    "Semantic validation failed: surface win/loss question should not include a round filter."
                )

        if "round = 'f'" in sql_l or "round='f'" in sql_l:
            if not cls._question_mentions_finals_or_titles(question):
                raise ValueError(
                    "Semantic validation failed: query filters to finals (round='F') but the question did not ask about finals/titles."
                )



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


def execute_sql_with_timeout_and_simplification(sql: str):
    """
    Executes SQL with timeout protection.
    If interrupted (timeout), attempts deterministic LLM simplification.
    Returns (final_sql_used, results) or raises exception.
    """
    try:
        results = run_query(sql)
        return sql, results

    except sqlite3.Error as e:
        msg = str(e)

        if "interrupted" in msg.lower():
            print("\n⏱️ Query timed out. Attempting automatic simplification...")

            simplified_sql = simplify_sql(sql)

            print("\n--- Simplified SQL ---\n")
            print(simplified_sql)

            validate_sql(simplified_sql)
            validate_schema(simplified_sql)

            results = run_query(simplified_sql)

            return simplified_sql, results
        else:
            raise

    except Exception:
        raise


def _ask_impl(question: str):
 # =========================
# Public engine entry point
# =========================
ENGINE = TennisGuruEngine()

def ask(question: str):
    """
    Public API-compatible wrapper.
    All external callers should use ask(),
    which delegates to the singleton ENGINE.
    """
    return ENGINE.process(question)
    # Step 0: Ask for clarification on subjective/ambiguous questions

    # Normalize question for caching
    normalized_q = question.strip().lower()

    # ==================================
    # Follow-up context handling
    # ==================================
    global LAST_CONTEXT

    followup_tournament_patterns = [
        "en que torneo",
        "en qué torneo",
        "which tournament",
        "what tournament"
    ]

    if any(p in normalized_q for p in followup_tournament_patterns):
        if LAST_CONTEXT["last_player_names"]:
            # If last query was same_tournament_multi_defeat,
            # reuse its core grouping logic to extract the exact tournament(s)
            if LAST_CONTEXT["last_sql"] and "HAVING COUNT(DISTINCT m.loser_id) = 3" in LAST_CONTEXT["last_sql"]:
                # Transform previous deterministic query into a winner_id + tourney_id subquery
                core_subquery = LAST_CONTEXT["last_sql"].replace(
                    "SELECT DISTINCT p.first_name, p.last_name",
                    "SELECT m.winner_id, m.tourney_id"
                )

                sql = f"""
SELECT DISTINCT m.tourney_name
FROM matches m
JOIN (
{core_subquery}
) sub
ON sub.winner_id = m.winner_id
AND sub.tourney_id = m.tourney_id;
""".strip()

            else:
                # Fallback: list tournaments won by last detected player
                first, last = LAST_CONTEXT["last_player_names"][0]

                sql = f"""
SELECT DISTINCT m.tourney_name
FROM matches m
JOIN players p ON p.player_id = m.winner_id
WHERE lower(p.first_name)=lower('{first}')
  AND lower(p.last_name)=lower('{last}');
""".strip()

            print("\n--- Generated SQL (contextual follow-up) ---\n")
            print(sql)

            try:
                validate_sql(sql)
                validate_schema(sql)
                results = run_query(sql)
            except Exception as e:
                print("\n❌ Context follow-up failed.")
                print(str(e))
                return

            print("\n--- Results ---\n")
            if not results:
                print("No results found.")
                return results

            for row in results:
                print(row[0])

            return results

    # Check cache first
    if normalized_q in QUERY_CACHE:
        cached = QUERY_CACHE[normalized_q]
        print("\n⚡ Cached result used (no LLM call, no DB hit).")
        print("\n--- Generated SQL ---\n")
        print(cached["sql"])
        print("\n--- Results ---\n")
        for row in cached["results"]:
            print(" | ".join(str(col) for col in row))
        return cached["results"]
    if is_question_ambiguous(question):
        print("\n⚠️ This question requires clarification before I can answer reliably.")

        print("\nPossible ambiguity types:")
        print("• Metric ambiguity (e.g., 'best player')")
        print("• Tournament scope ambiguity (e.g., 'record of most wins')")

        print("\nPlease clarify one of the following:")
        print("1) Tournament scope (ATP only, WTA only, Grand Slams only, Masters 1000, all levels)")
        print("2) Metric definition (peak rank, titles, win %, weeks at #1, etc.)")
        print("\nExample: 'ATP only' or 'Grand Slams only since 1990'.")

        return

    # =========================
    # INTENT ROUTER
    # =========================

    intent = classify_intent(question)

    deterministic_sql = None

    if intent == "same_tournament_multi_defeat":
        deterministic_sql = build_same_tournament_multi_defeat_query(question)

    elif intent == "ranking_at_final":
        deterministic_sql = build_final_ranking_query(question)

    if deterministic_sql:
        sql = deterministic_sql
        explanation = "Deterministic template handler."
        print("\n--- Generated SQL (deterministic) ---\n")
        print(sql)
        print("\n--- Explanation ---\n")
        print(explanation)
    else:
        # Step 1: Generate SQL via OpenAI
        try:
            sql, explanation = generate_sql_from_question(question, extra_rules="")
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

        # Step 1.5: Semantic guardrails
        try:
            SemanticGuard.validate(question, sql)
        except ValueError as sem_err:
            print("\n⚠️ Semantic validation failed. Applying automatic semantic correction...")
            print(str(sem_err))

            # If this is a surface win/loss query, strip any round filter deterministically
            if SemanticGuard._question_is_surface_wins_losses(question):
                # Remove any round = 'F' or round <> 'F' conditions
                sql = re.sub(r"\s+AND\s+round\s*(=|<>|!=)\s*'F'\s*", " ", sql, flags=re.IGNORECASE)
                sql = re.sub(r"round\s*(=|<>|!=)\s*'F'\s+AND\s+", "", sql, flags=re.IGNORECASE)

                # Enforce case-insensitive surface comparison:
                # Replace patterns like: surface = lower('clay')
                # With: lower(surface) = lower('clay')
                sql = re.sub(
                    r"\bsurface\s*=\s*lower\('([^']+)'\)",
                    r"lower(surface) = lower('\1')",
                    sql,
                    flags=re.IGNORECASE
                )

                # Also normalize plain surface = 'value'
                sql = re.sub(
                    r"\bsurface\s*=\s*'([^']+)'\b",
                    r"lower(surface) = lower('\1')",
                    sql,
                    flags=re.IGNORECASE
                )

                print("\n--- Corrected SQL (semantic auto-fix applied) ---\n")
                print(sql)
                print("\n--- Explanation ---\n")
                print("Round filter removed and surface comparison normalized for surface win/loss question.")
            else:
                # Fallback to LLM regeneration for other semantic errors
                retry_rules = (
                    "- Do NOT add any round filter unless the user explicitly asked for finals/titles.\n"
                    "- NEVER use round <> 'F' unless the user explicitly asked to exclude finals.\n"
                    "- For surface win/loss/played questions, do NOT include round filters.\n"
                )

                sql, explanation = generate_sql_from_question(question, extra_rules=retry_rules)

                print("\n--- Regenerated SQL ---\n")
                print(sql)
                print("\n--- Explanation ---\n")
                print("SQL regenerated after semantic validation.")

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

    try:
        SemanticGuard.validate(question, sql)
    except ValueError as sem_err:
        print("\n❌ Semantic validation failed.")
        print(str(sem_err))
        return

    # Step 2.5: Detect complex queries
    # (Removed per instructions)

    try:
        sql, results = execute_sql_with_timeout_and_simplification(sql)
    except sqlite3.Error as e:
        print("\n❌ Database execution error.")
        print(str(e))
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

        # Store in cache
        QUERY_CACHE[normalized_q] = {
            "sql": sql,
            "results": results
        }
        return results

    # If name pairs
    if len(results[0]) == 2 and all(isinstance(col, str) for col in results[0]):
        # Update conversational memory with detected player names
        LAST_CONTEXT["last_player_names"] = [(row[0], row[1]) for row in results]
        LAST_CONTEXT["last_sql"] = sql
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

        # Store in cache
        QUERY_CACHE[normalized_q] = {
            "sql": sql,
            "results": results
        }
        return results

    # =========================
    # Auto-resolve player_id for aggregated leader queries
    # =========================
    if (
        len(results) == 1
        and len(results[0]) == 2
        and isinstance(results[0][0], int)
        and isinstance(results[0][1], (int, float))
    ):
        player_id = results[0][0]
        metric_value = results[0][1]

        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute(
                "SELECT first_name, last_name FROM players WHERE player_id = ?",
                (player_id,)
            )
            player_row = cur.fetchone()
            conn.close()

            if player_row:
                first_name, last_name = player_row
                print(f"{first_name} {last_name} | {metric_value}")
                QUERY_CACHE[normalized_q] = {
                    "sql": sql,
                    "results": results
                }
                return results

        except Exception:
            pass

    # Fallback for generic tables
    for row in results:
        print(" | ".join(str(col) for col in row))

    # Update conversational memory if result contains player names (generic fallback)
    if results and len(results[0]) >= 2 and all(isinstance(col, str) for col in results[0][:2]):
        LAST_CONTEXT["last_player_names"] = [(row[0], row[1]) for row in results]
        LAST_CONTEXT["last_sql"] = sql

    # Store in cache
    QUERY_CACHE[normalized_q] = {
        "sql": sql,
        "results": results
    }
    return results


if __name__ == "__main__":
    engine = ENGINE

    while True:
        user_question = input("Ask Tennis Guru (or type 'exit'): ").strip()

        if not user_question:
            continue

        if user_question.lower() in {"exit", "quit", "q"}:
            print("Bye! 🎾")
            break

        engine.process(user_question)

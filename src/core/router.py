import re
import sqlite3
from .schema import DB_PATH

AMBIGUOUS_KEYWORDS = {
    "best player","most impressive","strongest era","most dominant","greatest",
    "strongest generation","best era","biggest upset","most impressive career",
    "who was better","who was more dominant",
}

RECORD_KEYWORDS = {
    "record","récord","most wins","most matches","most victories","all time leader",
    "all-time leader","record of most","record de mas","record de más",
    "mas partidos ganados","más partidos ganados",
}

SCOPE_KEYWORDS = {
    "grand slam","masters","masters 1000","atp","wta","challenger","futures",
    "roland garros","wimbledon","us open","australian open",
}

def is_question_ambiguous(question: str) -> bool:
    q = question.strip().lower()
    if any(k in q for k in AMBIGUOUS_KEYWORDS):
        return True
    if any(k in q for k in RECORD_KEYWORDS) and not any(s in q for s in SCOPE_KEYWORDS):
        return True
    return False

def classify_intent(question: str) -> str | None:
    q = question.lower()
    if (
        any(p in q for p in ["le gano a","le ganó a","derroto a","derrotó a","beat","defeated"])
        and ("mismo torneo" in q or "same tournament" in q)
    ):
        return "same_tournament_multi_defeat"

    if (
        ("final" in q or "final de" in q)
        and re.search(r"\b(19|20)\d{2}\b", question)
        and any(t in q for t in ["wimbledon","roland garros","us open","australian open"])
    ):
        return "ranking_at_final"

    return None

def build_same_tournament_multi_defeat_query(question: str) -> str | None:
    q_lower = question.lower()
    trigger_phrases = ["le gano a","le ganó a","derroto a","derrotó a","beat","defeated"]
    if not any(p in q_lower for p in trigger_phrases):
        return None
    if "mismo torneo" not in q_lower and "same tournament" not in q_lower:
        return None

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
        first, last = parts[0], parts[-1]
        cur.execute(
            """SELECT player_id FROM players
               WHERE lower(first_name)=lower(?) AND lower(last_name)=lower(?)""",
            (first, last),
        )
        if cur.fetchone():
            detected_players.append((first, last))

    conn.close()
    detected_players = list(dict.fromkeys(detected_players))
    if len(detected_players) < 3:
        return None

    full_names = detected_players[:3]
    opponent_subqueries = []
    for first, last in full_names:
        opponent_subqueries.append(f"""
        SELECT player_id FROM players
        WHERE lower(first_name)=lower('{first}')
          AND lower(last_name)=lower('{last}')
        """)
    union_block = "\nUNION\n".join(opponent_subqueries)

    return f"""
SELECT DISTINCT p.first_name, p.last_name
FROM matches m
JOIN players p ON p.player_id = m.winner_id
WHERE m.loser_id IN (
{union_block}
)
GROUP BY m.winner_id, m.tourney_id
HAVING COUNT(DISTINCT m.loser_id) = 3;
""".strip()

def build_final_ranking_query(question: str) -> str | None:
    q_lower = question.lower()
    if "final" not in q_lower and "final de" not in q_lower:
        return None

    year_match = re.search(r"\b(19|20)\d{2}\b", question)
    if not year_match:
        return None
    year = year_match.group(0)

    tourney_pattern = r"(Wimbledon|Roland Garros|US Open|Australian Open)"
    tourney_match = re.search(tourney_pattern, question, re.IGNORECASE)
    if not tourney_match:
        return None
    tourney_name = tourney_match.group(0)

    name_pattern = r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b"
    players = re.findall(name_pattern, question)
    if len(players) < 2:
        return None

    p1 = players[0].split()
    p2 = players[1].split()

    return f"""
SELECT
    (
        SELECT r.rank
        FROM rankings r
        WHERE r.player_id = (
            SELECT player_id FROM players
            WHERE lower(first_name)=lower('{p1[0]}')
              AND lower(last_name)=lower('{p1[-1]}')
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
            WHERE lower(first_name)=lower('{p2[0]}')
              AND lower(last_name)=lower('{p2[-1]}')
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

FOLLOWUP_TOURNEY_PATTERNS = [
    "en que torneo",
    "en qué torneo",
    "which tournament",
    "what tournament"
]

def is_followup_tourney_question(question: str, last_sql: str | None) -> bool:
    """
    Detects if this question is a contextual follow-up asking
    about the tournament of a previously computed multi-defeat query.
    """
    if not last_sql:
        return False

    q_norm = question.strip().lower()

    if not any(p in q_norm for p in FOLLOWUP_TOURNEY_PATTERNS):
        return False

    # Only allow deterministic follow-up if previous SQL was multi-defeat query
    if "HAVING COUNT(DISTINCT m.loser_id) = 3" in last_sql:
        return True

    return False


def build_followup_tourney_query(last_sql: str) -> str:
    """
    Builds deterministic SQL to retrieve tournament(s)
    from a previous multi-opponent defeat query.
    """
    core_subquery = last_sql.replace(
        "SELECT DISTINCT p.first_name, p.last_name",
        "SELECT m.winner_id, m.tourney_id"
    )

    return f"""
SELECT DISTINCT m.tourney_name
FROM matches m
JOIN (
{core_subquery}
) sub
ON sub.winner_id = m.winner_id
AND sub.tourney_id = m.tourney_id;
""".strip()
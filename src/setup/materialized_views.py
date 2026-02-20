import sqlite3


def build_match_rank_snapshot(db_path: str) -> None:
    """
    Creates match_rank_snapshot materialized table
    with ranking snapshot at match time.
    Only runs if table does not already exist.
    """

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if table already exists
    cursor.execute("""
        SELECT name 
        FROM sqlite_master 
        WHERE type='table' 
        AND name='match_rank_snapshot';
    """)

    if cursor.fetchone():
        print("match_rank_snapshot already exists. Skipping creation.")
        conn.close()
        return

    print("Creating match_rank_snapshot table...")

    cursor.execute("""
        CREATE TABLE match_rank_snapshot AS
        SELECT
            m.match_id,
            m.match_date,
            m.tour,
            m.tourney_level,
            m.round,
            m.surface,
            m.winner_id,
            m.loser_id,
            (
                SELECT r.rank
                FROM rankings r
                WHERE r.player_id = m.winner_id
                  AND r.gender = 'ATP'
                  AND r.ranking_date <= m.match_date
                ORDER BY r.ranking_date DESC
                LIMIT 1
            ) AS winner_rank,
            (
                SELECT r.rank
                FROM rankings r
                WHERE r.player_id = m.loser_id
                  AND r.gender = 'ATP'
                  AND r.ranking_date <= m.match_date
                ORDER BY r.ranking_date DESC
                LIMIT 1
            ) AS loser_rank
        FROM matches m
        WHERE m.tour = 'ATP';
    """)

    print("Creating indexes...")

    cursor.execute("CREATE INDEX idx_snapshot_match_id ON match_rank_snapshot(match_id);")
    cursor.execute("CREATE INDEX idx_snapshot_winner ON match_rank_snapshot(winner_id);")
    cursor.execute("CREATE INDEX idx_snapshot_loser ON match_rank_snapshot(loser_id);")
    cursor.execute("CREATE INDEX idx_snapshot_winner_rank ON match_rank_snapshot(winner_rank);")
    cursor.execute("CREATE INDEX idx_snapshot_loser_rank ON match_rank_snapshot(loser_rank);")
    cursor.execute("CREATE INDEX idx_snapshot_tour ON match_rank_snapshot(tour);")
    cursor.execute("CREATE INDEX idx_snapshot_level ON match_rank_snapshot(tourney_level);")
    cursor.execute("CREATE INDEX idx_snapshot_round ON match_rank_snapshot(round);")
    cursor.execute("CREATE INDEX idx_snapshot_surface ON match_rank_snapshot(surface);")

    conn.commit()
    conn.close()

    print("match_rank_snapshot created successfully.")
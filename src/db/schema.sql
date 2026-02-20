-- ========================================
-- Tennis Guru Database Schema
-- Phase 1: Ranking Engine
-- ========================================

-- Drop existing tables (safe for development)
DROP TABLE IF EXISTS rankings;

-- ========================================
-- Rankings Table
-- ========================================
-- Stores official weekly ranking snapshots
-- for ATP and WTA players
-- ========================================

CREATE TABLE rankings (
    player_id INTEGER NOT NULL,
    ranking_date DATE NOT NULL,
    rank INTEGER NOT NULL,
    points INTEGER,
    gender TEXT NOT NULL CHECK (gender IN ('ATP', 'WTA')),
    
    -- Composite primary key ensures
    -- one ranking per player per week per tour
    PRIMARY KEY (player_id, ranking_date, gender)
);

-- ========================================
-- Index for fast temporal lookup
-- Critical for ranking-at-match queries
-- ========================================

CREATE INDEX idx_rank_lookup
ON rankings (player_id, gender, ranking_date DESC);

-- ========================================
-- Players Table
-- ========================================

DROP TABLE IF EXISTS players;

CREATE TABLE players (
    player_id INTEGER NOT NULL,
    first_name TEXT,
    last_name TEXT,
    gender TEXT NOT NULL CHECK (gender IN ('ATP', 'WTA')),
    hand TEXT,
    dob DATE,
    country TEXT,
    height INTEGER,
    PRIMARY KEY (player_id, gender)
);

CREATE INDEX idx_players_name
ON players (last_name, first_name);

-- ========================================
-- Matches Table
-- ========================================

DROP TABLE IF EXISTS matches;

CREATE TABLE matches (
    match_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    tour TEXT NOT NULL CHECK (tour IN ('ATP', 'WTA')),
    
    tourney_id TEXT,
    tourney_name TEXT,
    surface TEXT,
    tourney_level TEXT,
    
    match_date DATE NOT NULL,
    round TEXT,
    best_of INTEGER,
    
    winner_id INTEGER NOT NULL,
    loser_id INTEGER NOT NULL,
    
    winner_rank INTEGER,
    loser_rank INTEGER,

    w_ace INTEGER,
    l_ace INTEGER,
    
    score TEXT
);

--

CREATE INDEX IF NOT EXISTS idx_rankings_player_date 
ON rankings(player_id, ranking_date);

CREATE INDEX IF NOT EXISTS idx_rankings_rank_gender 
ON rankings(rank, gender);

CREATE INDEX IF NOT EXISTS idx_matches_winner 
ON matches(winner_id);

CREATE INDEX IF NOT EXISTS idx_matches_loser 
ON matches(loser_id);

CREATE INDEX IF NOT EXISTS idx_matches_tourney_level 
ON matches(tourney_level);

CREATE INDEX IF NOT EXISTS idx_matches_round 
ON matches(round);

--


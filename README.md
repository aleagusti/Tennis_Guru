# 🎾 Tennis Guru — Deterministic Natural Language to SQL Engine

Tennis Guru is a deterministic Natural Language → SQL engine built on top of a structured ATP dataset (matches, players, rankings).

It allows users to ask tennis-related questions in natural language and generates safe, executable SQL queries against a SQLite database.

This project focuses on:

- Deterministic SQL generation  
- Strict rule enforcement  
- Benchmark-driven evaluation  
- Reproducibility  
- Cost-efficient LLM usage  

Current status: **v1.0 — Stable Deterministic Engine + Web Demo**

---

## 🧠 What This Project Solves

Large Language Models frequently:

- Over-generalize queries  
- Ignore domain constraints  
- Produce non-reproducible results  
- Fail silently under complex joins  

Tennis Guru enforces:

- Structured prompt rules  
- Domain-specific constraints  
- Controlled SQL generation  
- Deterministic outputs (temperature = 0)  
- Benchmark validation  
- Timeout protection  
- Explicit clarification for ambiguous questions  

This is not a chatbot demo.  
It is a reproducible NL→SQL engineering benchmark system.

---

## 📊 Dataset

SQLite database: `data/guru.db`

Source:

- ATP historical match and ranking data sourced from Jeff Sackmann’s open tennis datasets  
  https://github.com/JeffSackmann

The dataset is publicly available and free to use.

Core tables:

- `players`
- `matches`
- `rankings`

Key features:

- Historical ranking snapshots computed dynamically
- Temporal ranking joins (latest ranking before match date)
- ATP-only filtering enforced by default (WTA queries must be explicitly specified)
- Controlled join logic for negative queries
- No implicit cross joins allowed

---

### Data Attribution

This project uses publicly available historical tennis data compiled by Jeff Sackmann.

All credit for data collection and maintenance belongs to the original author.  
This repository only restructures and loads the data into a local SQLite database for analytical purposes.

---

---

## ⚙️ Architecture

The project follows a strict **single-turn deterministic NL → SQL pipeline** design.

It separates responsibilities clearly between:

- Intent routing  
- LLM generation  
- SQL transformation  
- Domain enforcement  
- Safe execution  
- Benchmark validation  

---

### High-Level Flow

```
User Question
      ↓
Intent Classification (router)
      ↓
LLM Generator (gpt-4.1-mini, temperature=0)
      ↓
SQL Transformer (structural normalization)
      ↓
Semantic Guard (domain constraints)
      ↓
SQLite Executor
      ↓
Result
```

---

### Project Structure

```
tennis-guru/
│
├── app/
│   └── app.py                     # Streamlit web demo interface
│
├── cli/
│   └── nl_query.py                # Interactive CLI
│
├── data/
│   └── guru.db                    # SQLite database
│
├── logs/
│   └── query_benchmark.json       # Benchmark output
│
├── src/
│   ├── core/
│   │   ├── engine.py              # Orchestrates full pipeline
│   │   ├── llm_generator.py       # Calls OpenAI model
│   │   ├── sql_transformer.py     # SQL rewriting & normalization
│   │   ├── semantic_guard.py      # Domain rule enforcement
│   │   ├── sql_executor.py        # Executes SQL safely
│   │   ├── router.py              # Intent classification
│   │   ├── schema.py              # DB schema metadata + table allowlist for the LLM prompt
│   │   └── cache.py               # Query caching
│   │
│   ├── db/
│   │   ├── init_db.py             # Database initialization
│   │   ├── rebuild_snapshot.py    # Ranking snapshot rebuild
│   │   └── schema.sql             # SQL schema definition
│   │
│   ├── ingest/
│   │   ├── load_matches.py
│   │   ├── load_players.py
│   │   └── load_rankings.py
│   │
│   └── setup/
│       └── materialized_views.py  # Snapshot logic
│
├── tests/
│   └── run_benchmark.py           # Automated benchmark runner
│
├── changelog.md
├── requirements.txt
├── Roadmap.md
└── README.md
```

---

### Architectural Notes (v1.0)

- The engine is intentionally **single-turn only**.
- No conversational memory or follow-up state is maintained.
- All queries are generated deterministically with temperature = 0.
- Benchmark validation is part of the core system design.
- Ambiguous or subjective questions are flagged instead of hallucinated.
- A lightweight Streamlit UI layer for portfolio demonstration.
- Dynamic SQL alias parsing for automatic result table headers.
- Match statistics (w_/l_ prefixed columns) fully supported in aggregation logic.

The structure prioritizes:

- Determinism  
- Traceability  
- Controlled complexity  
- Reproducibility  

over feature bloat.

---

## 🔒 Deterministic SQL Rules

The engine enforces strict domain rules:

- Always filter `m.tour = 'ATP'`
- Always filter `p.gender = 'ATP'`
- No broadening of tournament levels
- Ranking queries must use temporal subquery
- Negative logic must use `LEFT JOIN + IS NULL`
- No uncontrolled `EXISTS`
- No implicit cross joins
- Match statistics are split by side (`w_` = winner, `l_` = loser) and must be aggregated using CASE over `winner_id` / `loser_id`.
- Multi-metric aggregation queries (titles, matches, aces) are supported in a single deterministic query.

Temperature is fixed to 0 to ensure reproducibility.

---

## 🧪 Benchmark System

Location:

```
tests/run_benchmark.py
```

The benchmark:

- Runs 28 structured questions (L1–L5)
- Measures:
  - LLM generation time
  - SQL execution time
  - Clarifications
  - Timeouts
  - Errors
- Stores results in:

```
logs/query_benchmark.json
```

JSON structure:

```
{
  "summary": { ... },
  "results": [ ... ]
}
```

This enables:

- Model comparison (mini vs pro)
- Performance tracking
- Regression detection
- Reproducible evaluation

---

## 📈 Current Performance (v1.0)

- 28 benchmark questions
- 100% executable SQL for objective questions
- 0 SQL syntax errors
- Deterministic outputs
- Subjective questions correctly flagged for clarification
- Average generation time ≈ 3 seconds (mini model)
- Stable multi-column aggregation (titles, matches, aces) validated in benchmark and UI

---

## 🚀 Running the Project

### Requirements

- Python 3.10+
- SQLite
- OpenAI API key (paid API usage required)

⚠️ The OpenAI API is a paid service. Running the NL→SQL engine requires a valid API key with billing enabled.

Initialize database:

```
python src/db/init_db.py
```

Rebuild ranking snapshot (if needed):

```
python src/db/rebuild_snapshot.py
```


Run CLI:

```
python cli/nl_query.py
```

### Run Benchmark (Technical Evaluation)

```
python tests/run_benchmark.py
```

This runs the full structured benchmark suite and stores results in `logs/query_benchmark.json`, including summary metrics and per-question diagnostics.

### Run Web Demo (Streamlit)

```
streamlit run app/app.py
```

This launches the portfolio-ready web interface with dynamic result rendering.

---

## 🧩 Example Query

Question:

```
How many matches did Federer win while ranked number 1?
```

Generated SQL:

```
SELECT COUNT(*) AS matches_won_while_rank_1
FROM matches m
JOIN players p ON p.player_id = m.winner_id
JOIN rankings r ON r.player_id = m.winner_id
               AND r.gender = 'ATP'
               AND r.ranking_date = (
                   SELECT MAX(r2.ranking_date)
                   FROM rankings r2
                   WHERE r2.player_id = r.player_id
                     AND r2.gender = 'ATP'
                     AND r2.ranking_date <= m.match_date
               )
WHERE p.gender = 'ATP'
  AND lower(p.first_name) = 'roger'
  AND lower(p.last_name) = 'federer'
  AND m.tour = 'ATP'
  AND r.rank = 1;
```

Result:

```
434
```

---

### 🔎 Example: Multi-Step Query Decomposition (Manual)

Some analytical questions are naturally multi-step and can be decomposed into separate queries for clarity and performance.

For example:

**Question 1**

```
When did Roger Federer win his first Grand Slam?
```

Generated SQL:

```
SELECT MIN(m.match_date) AS first_grand_slam_win_date
FROM matches m
JOIN players p ON p.player_id = m.winner_id
WHERE p.gender = 'ATP'
  AND lower(p.first_name) = 'roger'
  AND lower(p.last_name) = 'federer'
  AND m.tour = 'ATP'
  AND m.round = 'F'
  AND m.tourney_level = 'G';
```

Result:

```
2003-06-23
```

---

**Question 2**

```
Name the list of top ten players at 2003-06-24
```

Generated SQL:

```
SELECT p.first_name, p.last_name, r.rank, r.points
FROM rankings r
JOIN players p ON p.player_id = r.player_id
WHERE r.ranking_date = (
    SELECT MAX(r2.ranking_date)
    FROM rankings r2
    WHERE r2.ranking_date <= '2003-06-24'
      AND r2.gender = 'ATP'
)
  AND r.rank <= 10
  AND r.gender = 'ATP'
  AND p.gender = 'ATP'
ORDER BY r.rank ASC;
```

Result:

```
Andre Agassi - 1 - 3975
Lleyton Hewitt - 2 - 3940
Juan Carlos Ferrero - 3 - 3760
Carlos Moya - 4 - 3160
Roger Federer - 5 - 2580
Andy Roddick - 6 - 2390
Guillermo Coria - 7 - 2260
Rainer Schuettler - 8 - 1925
David Nalbandian - 9 - 1895
Jiri Novak - 10 - 1805
```

This illustrates how complex temporal questions can be answered deterministically by decomposing them into smaller, logically consistent steps.

The engine is intentionally single-turn in v1.0, but this pattern demonstrates how users can obtain precise analytical answers through controlled query sequencing.

---

## 🏷 Versioning

v1.0 — Stable deterministic SQL engine

- Ranking logic stabilized  
- Benchmark summary integrated  
- JSON reporting standardized  
- Single-turn architecture enforced  
- No conversational state  

---

## 📌 Future Improvements

- SQLite index optimization
- Cost/token tracking per benchmark run
- Cross-model automatic comparison
- Ranking materialized view optimization
- Expanded benchmark question suite
- Query plan inspection logging

---

## 👤 Author

Alejandro Agusti  
Data Product / ML / Energy Logistics  
https://www.linkedin.com/in/alejandro-agusti1/

Built as a reproducible NL→SQL benchmark engine.

# Changelog

All notable changes to this project will be documented in this file.

This project follows Semantic Versioning:
MAJOR.MINOR.PATCH

---

## [0.3.0] - 2026-02-17

### Added
- Deterministic intent routing layer (same tournament multi-defeat, ranking at final, contextual follow-ups)
- Semantic auto-correction layer (surface win/loss validation and automatic round filter removal)
- Context memory system (`LAST_CONTEXT`) for follow-up questions
- Intent classification system with centralized router
- Deterministic SQL templates for complex historical queries

### Refactored
- Split monolithic `nl_query.py` into modular architecture:
  - `engine.py`
  - `router.py`
  - `semantic_guard.py`
  - `llm_generator.py`
  - `sql_executor.py`
  - `cache.py`
  - `context.py`
- Introduced orchestration engine (`TennisGuruEngine`)
- Separated CLI layer from core engine logic
- Improved error propagation and structured result handling

### Improved
- Surface-based queries (clay/grass/hard/carpet) now correctly avoid unintended round filters
- Follow-up tournament queries now use contextual SQL instead of re-inferencing entities
- Reduced false simplifications and over-aggressive query rewriting
- More robust semantic validation flow

---

## [0.2.2] - 2026-02-14

### Added
- Interactive REPL loop (persistent CLI session)
- Schema validation fixes (string literal detection)
- Improved caching layer with normalized question keys

### Improved
- Removed premature program termination after single query
- Stabilized SQL generation pipeline
- Reduced unnecessary LLM calls through cache usage

---

## [0.2.0] - 2026-02-13

### Added
- Query result caching layer in `nl_query.py`
- Benchmark integration compatibility
- Structured benchmark logging (SQL, result sample, metadata)

### Improved
- Query execution performance for repeated questions
- Internal architecture prepared for modular scaling

---

## [0.1.0] - 2026-02-13

### Added
- Natural Language → SQL generation using OpenAI API
- Schema-aware prompt construction
- SQL validation layer (SELECT-only enforcement)
- Complexity detector
- Automatic query simplification fallback
- Timeout protection for long-running queries
- Ambiguity detection layer
- Basic result formatting

### Infrastructure
- SQLite database with rankings, matches and players tables
- Historical ATP/WTA data ingestion
- Initial benchmark harness (`run_benchmark.py`)
- Stress test suite with difficulty levels (L1–L5)

---

## Pre-versioning Phase

### Initial Build
- Repository creation
- Database schema design
- Rankings ingestion
- Matches ingestion
- Players ingestion
- First successful temporal ranking query
- First complex opponent-rank query (Federer vs Top 5 in finals)

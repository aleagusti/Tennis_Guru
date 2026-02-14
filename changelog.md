

# Changelog

All notable changes to this project will be documented in this file.

This project follows Semantic Versioning:
MAJOR.MINOR.PATCH

---

## [0.2.0] - 2026-02-13

### Added
- Query result caching layer in `nl_query.py`
- Benchmark integration compatibility
- Structured benchmark logging (SQL, result sample, metadata)

### Improved
- Query execution performance for repeated questions
- Internal architecture modularization for future scaling

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

# 🟢 STAGE A — Historical Core Engine (Base sólida)

🎯 Objetivo: Motor histórico confiable y publicable.

A1 — Performance
	•	Indexes versioned in schema.sql
	•	Add query execution timer
	•	Add optional EXPLAIN QUERY PLAN debug mode
	•	Detect and reject extremely expensive queries
	•	Add structured logging (question, SQL, execution time, simplification triggered)
	•	Add query benchmark runner
	•	Track LLM generation time separately from SQL execution time

A2 — Semantic Quality
	•	Ranking “at the time” rule
	•	Grand Slam rule
	•	Force JOIN to players when returning identities
	•	Add anti-pattern detection (e.g., ranking_date = match_date)

A3 — UX Improvements
	•	Format numeric results cleanly
	•	Format player name results nicely
	•	Detect result type automatically
	•	Respond in same language as user

A4 — Robustness
	•	API error handling
	•	SQL validation
	•	Add execution timeout
	•	Add max-row safeguard
	•	Add retry with exponential backoff for OpenAI RateLimitError
	•	Add debug mode (--raw, --debug)
	•	Persist query history to logs/query_history.json


👉 Resultado del Stage A:
Un motor histórico robusto, presentable en portfolio serio.

---

# 🔥 HIGH PRIORITY — Architectural Refactor (Technical Debt Reduction)

🎯 Objetivo: Profesionalizar la arquitectura interna antes de seguir agregando features.

HP1 — Modularization (Refactor estructural)
	•	Split nl_query.py into modules:
		•	intent_router.py
		•	deterministic_handlers.py
		•	llm_generator.py
		•	semantic_validator.py
		•	sql_validator.py
		•	executor.py
		•	memory.py
	•	Keep nl_query.py as lightweight orchestrator (CLI + engine bootstrap)
	•	Reduce monolithic file complexity
	•	Enable unit testing per module

HP2 — Intent Registry System
	•	Replace conditional intent routing with INTENT_REGISTRY dict
	•	Map intent → handler function
	•	Remove large if/elif chains
	•	Make new deterministic templates plug‑and‑play

HP3 — Context Memory Redesign
	•	Store structured context:
		•	last_intent
		•	last_entities
		•	last_tourney
		•	last_year
	•	Stop relying on raw SQL string matching
	•	Improve follow‑up question reliability

HP4 — SQL Parsing Upgrade
	•	Replace fragile regex validation with sqlparse-based inspection
	•	Detect:
		•	unwanted round filters
		•	missing JOIN to players
		•	dangerous patterns
	•	Improve robustness of semantic corrections

HP5 — Engine Class Abstraction
	•	Create TennisGuruEngine class
	•	Move orchestration logic into process(question)
	•	Allow future:
		•	API integration
		•	Web UI reuse
		•	Unit testing without CLI

👉 Resultado del HIGH PRIORITY block:
Base arquitectónica sólida, mantenible y escalable antes de continuar con expansión funcional.

---

# 🔵 STAGE A+ — Research & Benchmark Layer

🎯 Objetivo: Medir capacidad real de razonamiento NL → SQL y documentar performance.

A+1 — Stress Test Suite
	•	Create tests/stress_tests.txt
	•	Categorize questions by reasoning difficulty (Level 1–5)
	•	Include negative logic, temporal logic, aggregations, comparisons

A+2 — Benchmark Runner
	•	Create tests/run_benchmark.py
	•	Execute all stress questions automatically
	•	Measure:
		•	LLM generation time
		•	SQL execution time
		•	Simplification triggered (yes/no)
		•	Timeout occurrences
		•	Empty result anomalies
	•	Persist results to logs/query_benchmark.json

A+3 — Metrics & Evaluation
	•	Compute average execution time
	•	Compute simplification rate
	•	Compute failure rate
	•	Identify worst-performing queries
	•	Generate summary report for README

👉 Resultado del Stage A+:
Motor evaluado experimentalmente con métricas objetivas de razonamiento y performance.

# 🟡 STAGE B — Statistical Expansion

🎯 Objetivo: Agregar estadísticas avanzadas.

Necesita ampliar dataset.

B1 — Extender schema

Agregar columnas como:
	•	aces
	•	double faults
	•	break points won
	•	service games won
	•	etc.

(Jeff Sackmann tiene estos datos en algunos CSV)

B2 — Stats-level queries

Permitir preguntas como:
	•	“Jugador con más aces”
	•	“Mejor porcentaje de quiebre”
	•	“Mayor win rate en clay”
	•	“Head-to-head Federer vs Nadal en GS”

B3 — Métricas derivadas
	•	Win rate
	•	Títulos por superficie
	•	Promedios históricos
	•	Performance por era

👉 Resultado del Stage B:
Motor estadístico comparable a ATP Stats.

# 🔴 STAGE C — Full Product Layer

🎯 Objetivo: Convertirlo en producto real.

C1 — API
POST /query

C2 — Web UI
	•	Streamlit
	•	O React + backend
	•	Visualizaciones

C3 — Conversational Memory
	•	Follow-up questions:
	•	“¿Y en clay?”
	•	“¿Y solo Grand Slams?”

C4 — Query Optimizer Agent
	•	LLM genera SQL
	•	Motor analiza costo
	•	Reescribe si es ineficiente

C5 — Deploy
	•	Docker
	•	Railway / Render / Fly.io
	•	Hosting público

👉 Resultado del Stage C:
Tennis Guru como producto web consultable públicamente.

---

# 🟣 STAGE C+ — Entity Resolution & Semantic Layer

🎯 Objetivo: Resolver ambigüedad semántica y profesionalizar el motor NL → SQL.

C+1 — Player Resolution Layer
	•	Detect player entities before SQL generation
	•	If only one token detected → treat as last_name
	•	Query DB to resolve player_id before LLM SQL execution
	•	If 0 matches → return “Player not found”
	•	If 1 match → inject explicit player_id into SQL
	•	If multiple matches → ask clarification question
	•	Eliminate subqueries like:
		(SELECT player_id FROM players WHERE ...)
	•	Replace with explicit ID filters for performance and determinism

C+2 — Ambiguity Detection Framework
	•	Detect vague terms (best, dominant, strongest era, etc.)
	•	Require metric definition before SQL execution
	•	Add clarification-first workflow
	•	Track clarification rate in benchmark

C+3 — Deterministic Entity Injection
	•	Pre-resolve entities in Python
	•	Inject resolved IDs into final SQL
	•	Reduce LLM hallucination risk
	•	Improve performance and cache efficiency

👉 Resultado del Stage C+:
Motor semánticamente robusto con resolución determinística de entidades, listo para nivel producto profesional.
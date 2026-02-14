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
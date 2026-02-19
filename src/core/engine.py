from dataclasses import dataclass
from typing import Optional, List, Tuple, Any

from .cache import QUERY_CACHE
from .context import LAST_CONTEXT
from .router import (
    classify_intent,
    is_question_ambiguous,
    is_followup_tourney_question,
    build_same_tournament_multi_defeat_query,
    build_final_ranking_query,
    build_followup_tourney_query,
)
from .semantic_guard import SemanticGuard
from .llm_generator import generate_sql_from_question, generate_nl_answer
from .sql_executor import execute_sql
from .sql_transformer import SQLTransformer



@dataclass
class EngineResult:
    question: str
    # Final SQL actually executed (after semantic + structural transforms)
    sql: Optional[str] = None
    # Raw SQL returned by the LLM before transformations
    generated_sql: Optional[str] = None
    # Query results
    results: Optional[List[Tuple[Any, ...]]] = None
    # Human-readable explanation of how SQL was produced
    explanation: Optional[str] = None

    # Timing (seconds) for LLM generation only (None when deterministic/cached)
    llm_generation_time: Optional[float] = None

    # Metadata flags
    cached: bool = False
    needs_clarification: bool = False
    error: Optional[str] = None
    followup: bool = False


class TennisGuruEngine:
    """
    Orchestrates the full pipeline:
    - cache lookup
    - ambiguity detection
    - deterministic routing (when applicable)
    - LLM generation
    - semantic normalization (lightweight)
    - structural SQL transformation (policy layer)
    - execution
    - context update
    """

    def process(self, question: str) -> EngineResult:
        q_norm = question.strip().lower()

        # =============================
        # 1) Cache
        # =============================
        if q_norm in QUERY_CACHE:
            cached = QUERY_CACHE[q_norm]
            return EngineResult(
                question=question,
                sql=cached["sql"],
                results=cached["results"],
                explanation="Cached result.",
                llm_generation_time=None,
                cached=True,
            )

        # =============================
        # 2) Ambiguity detection
        # =============================
        if is_question_ambiguous(question):
            return EngineResult(
                question=question,
                sql=None,
                results=None,
                explanation=None,
                llm_generation_time=None,
                needs_clarification=True,
                error="Ambiguous question: please clarify scope or metric.",
            )

        # =============================
        # 3) Follow-up routing
        # =============================
        if is_followup_tourney_question(question, LAST_CONTEXT.get("last_sql")):
            try:
                sql = build_followup_tourney_query(LAST_CONTEXT["last_sql"])
                results = execute_sql(sql, timeout_seconds=30)
                return EngineResult(
                    question=question,
                    sql=sql,
                    results=results,
                    explanation="Contextual follow-up (deterministic).",
                    llm_generation_time=None,
                    followup=True,
                )
            except Exception as e:
                return EngineResult(
                    question=question,
                    sql=None,
                    results=None,
                    explanation=None,
                    llm_generation_time=None,
                    followup=True,
                    error=str(e),
                )

        # =============================
        # 4) Deterministic routing
        # =============================
        intent = classify_intent(question)
        sql = None
        explanation = None
        llm_time = None

        if intent == "same_tournament_multi_defeat":
            sql = build_same_tournament_multi_defeat_query(question)
            explanation = "Deterministic template: same-tournament multi-opponent defeat."

        elif intent == "ranking_at_final":
            sql = build_final_ranking_query(question)
            explanation = "Deterministic template: ranking at specific final."

        # =============================
        # 5) LLM fallback
        # =============================
        if not sql:
            try:
                sql, explanation, llm_time = generate_sql_from_question(question)
            except Exception as e:
                return EngineResult(
                    question=question,
                    sql=None,
                    results=None,
                    explanation=None,
                    llm_generation_time=None,
                    error=str(e),
                )

        # =============================
        # 6) Semantic validation + structural rewrite
        # =============================
        generated_sql = sql
        try:
            sql = SemanticGuard.validate_and_autofix(question, sql)
            # Structural transformation layer (policy enforcement)
            sql = SQLTransformer.rewrite_structural(sql)
        except Exception as e:
            return EngineResult(
                question=question,
                sql=sql,
                generated_sql=generated_sql,
                results=None,
                explanation=explanation,
                llm_generation_time=llm_time,
                error=str(e),
            )

        # =============================
        # 7) Execute SQL
        # =============================
        # Debug: print final SQL before execution
        print("\n--- FINAL SQL ---\n")
        print(sql)
        try:
            results = execute_sql(sql, timeout_seconds=30)
        except Exception as e:
            return EngineResult(
                question=question,
                sql=sql,
                generated_sql=generated_sql,
                results=None,
                explanation=explanation,
                llm_generation_time=llm_time,
                error=str(e),
            )

        # =============================
        # 8) Update context + cache
        # =============================
        LAST_CONTEXT["last_sql"] = sql
        LAST_CONTEXT["last_intent"] = intent

        # Store last player names if result looks like names
        if results and len(results[0]) >= 2 and all(isinstance(col, str) for col in results[0][:2]):
            LAST_CONTEXT["last_player_names"] = [(r[0], r[1]) for r in results]

        QUERY_CACHE[q_norm] = {
            "sql": sql,
            "results": results,
        }

        return EngineResult(
            question=question,
            sql=sql,
            generated_sql=generated_sql,
            results=results,
            explanation=explanation,
            llm_generation_time=llm_time,
        )


def format_for_cli(res: EngineResult) -> str:
    if res.needs_clarification:
        return f"⚠️ Necesito clarificación: {res.error}"

    if res.error:
        return f"❌ Error:\n\n{res.error}"

    if not res.results:
        return "No results found."

    # Single numeric value
    if (
        len(res.results) == 1
        and len(res.results[0]) == 1
        and isinstance(res.results[0][0], (int, float))
    ):
        try:
            return generate_nl_answer(res.question, res.results[0][0])
        except Exception:
            return str(res.results[0][0])

    # Two string columns (names)
    if len(res.results[0]) == 2 and all(isinstance(c, str) for c in res.results[0]):
        return ", ".join(f"{a} {b}" for a, b in res.results)

    # Generic table output
    lines = [" | ".join(str(c) for c in row) for row in res.results[:100]]
    return "\n".join(lines)

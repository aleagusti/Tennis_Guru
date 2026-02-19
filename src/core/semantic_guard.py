import re


class SemanticGuard:
    """
    Minimal semantic guard.

    Responsibilities:
    - Basic SQL hygiene (strip trailing semicolons)
    - Light literal normalization (surface synonyms only)

    It does NOT:
    - Inject filters
    - Rewrite structural SQL (EXISTS / JOIN logic)
    - Modify business logic
    - Interpret negative logic

    Structural rewrites now live in sql_transformer.py
    """

    @staticmethod
    def _normalize_surface_literals(question: str, sql: str) -> str:
        """
        Non-invasive normalization of surface literals.

        If the question clearly refers to a surface synonym,
        normalize existing surface comparisons to canonical values.

        This method never injects new filters.
        It only rewrites existing surface = 'X' comparisons.
        """

        q = question.lower()

        surface_map = {
            "clay": ["tierra batida", "polvo de ladrillo", "arcilla", "clay", "tierra"],
            "grass": ["hierba", "césped", "cesped", "grass"],
            "hard": ["cancha dura", "cemento", "dura", "hard"],
            "carpet": ["carpet"],
        }

        detected = None
        for canonical, synonyms in surface_map.items():
            for s in synonyms:
                if re.search(r"\b" + re.escape(s) + r"\b", q):
                    detected = canonical
                    break
            if detected:
                break

        if not detected:
            return sql

        # Rewrite only existing surface comparisons (lower(surface) = lower('X'))
        sql = re.sub(
            r"(lower\s*\(\s*surface\s*\)\s*=\s*lower\s*\(\s*'[^']+'\s*\))",
            f"lower(surface) = lower('{detected}')",
            sql,
            flags=re.IGNORECASE,
        )

        # Rewrite plain surface = 'X'
        sql = re.sub(
            r"\bsurface\s*=\s*'[^']+'",
            f"surface = '{detected}'",
            sql,
            flags=re.IGNORECASE,
        )

        return sql

    @staticmethod
    def validate_and_autofix(question: str, sql: str) -> str:
        """
        Minimal post-processing layer.
        """

        if not sql:
            return sql

        # 1) Basic hygiene
        corrected_sql = sql.strip().rstrip(";")

        # 2) Light surface normalization
        corrected_sql = SemanticGuard._normalize_surface_literals(
            question,
            corrected_sql,
        )

        return corrected_sql
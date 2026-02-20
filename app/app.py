#streamlit run app/app.py

import sys
from pathlib import Path

# Ensure project root is in Python path (so `src` can be imported)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import time
import pandas as pd
from src.core.engine import TennisGuruEngine

# Page config
st.set_page_config(
    page_title="Tennis Guru",
    page_icon="🎾",
    layout="wide"
)

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1.25rem;
        }
    </style>
    """,
    unsafe_allow_html=True
)

engine = TennisGuruEngine()

st.title("🎾 Tennis Guru")
st.caption("Deterministic Natural Language → SQL Engine (v1.0)")

# Input box
question = st.text_input("Ask a question about ATP history")

if st.button("Run Query") and question:

    start_time = time.time()

    with st.spinner("Generating SQL and executing query..."):
        result = engine.process(question)

    total_time = time.time() - start_time

    # Display results first
    st.subheader("Results")

    if result.results:
        # Convert results to DataFrame
        df = pd.DataFrame(result.results)

        # Try to derive column names from SQL aliases (SELECT ... AS alias)
        column_names = []
        if result.sql and "select" in result.sql.lower():
            try:
                select_part = result.sql.lower().split("from")[0]
                select_part = select_part.replace("select", "").strip()
                raw_cols = select_part.split(",")

                for col in raw_cols:
                    col = col.strip()
                    if " as " in col:
                        alias = col.split(" as ")[-1].strip()
                        column_names.append(alias.replace("_", " ").title())
                    else:
                        # fallback: use last token after dot
                        base = col.split(".")[-1]
                        column_names.append(base.replace("_", " ").title())
            except Exception:
                column_names = []

        # Apply derived names if they match the dataframe width
        if column_names and len(column_names) == df.shape[1]:
            df.columns = column_names
        else:
            # Fallback generic headers
            df.columns = [f"Column {i+1}" for i in range(df.shape[1])]

        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No results returned.")

    # Then display SQL in an expander
    with st.expander("SQL (click to view)", expanded=False):
        st.code(result.sql, language="sql")

    # Metadata
    st.markdown("---")
    st.write(f"⏱ Execution time: {round(total_time, 2)} seconds")
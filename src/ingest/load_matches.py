import pandas as pd
import sqlite3
from pathlib import Path

DB_PATH = Path("data/guru.db")
RAW_PATH = Path("data/raw")

def load_matches_for_tour(tour_folder, gender):
    dfs = []

    folder_path = RAW_PATH / tour_folder
    files = sorted(
    f for f in folder_path.glob(f"{tour_folder.split('_')[1]}_matches_*.csv")
    if "doubles" not in f.name
    and "futures" not in f.name
    and "qual" not in f.name
    and "amateur" not in f.name
    )

    for file_path in files:
        if "current" in file_path.name:
            continue  # evitar posibles duplicados

        print(f"Loading {file_path.name}...")
        df = pd.read_csv(file_path)

        if "w_ace" not in df.columns:
            df["w_ace"] = None
        if "l_ace" not in df.columns:
            df["l_ace"] = None

        df["w_ace"] = pd.to_numeric(df["w_ace"], errors="coerce")
        df["l_ace"] = pd.to_numeric(df["l_ace"], errors="coerce")
        
        df["match_date"] = pd.to_datetime(df["tourney_date"], format="%Y%m%d", errors="coerce")
        df["tour"] = gender

        dfs.append(df)

    return pd.concat(dfs, ignore_index=True)


def main():
    conn = sqlite3.connect(DB_PATH)

    # ATP
    print("Loading ATP matches...")
    atp_df = load_matches_for_tour("tennis_atp", "ATP")

    atp_clean = atp_df[[
        "tour",
        "tourney_id",
        "tourney_name",
        "surface",
        "tourney_level",
        "match_date",
        "round",
        "best_of",
        "winner_id",
        "loser_id",
        "winner_rank",
        "loser_rank",
        "w_ace",
        "l_ace",
        "score"
    ]].copy()
    atp_clean = atp_clean[atp_clean["match_date"].notna()]

    atp_clean.to_sql("matches", conn, if_exists="append", index=False)

    # WTA
    print("Loading WTA matches...")
    wta_df = load_matches_for_tour("tennis_wta", "WTA")

    wta_clean = wta_df[[
        "tour",
        "tourney_id",
        "tourney_name",
        "surface",
        "tourney_level",
        "match_date",
        "round",
        "best_of",
        "winner_id",
        "loser_id",
        "winner_rank",
        "loser_rank",
        "w_ace",
        "l_ace",
        "score"
    ]].copy()
    wta_clean = wta_clean[wta_clean["match_date"].notna()]

    wta_clean.to_sql("matches", conn, if_exists="append", index=False)

    conn.close()

    print("Matches loaded successfully.")
    print(f"ATP matches: {len(atp_clean)}")
    print(f"WTA matches: {len(wta_clean)}")


if __name__ == "__main__":
    main()
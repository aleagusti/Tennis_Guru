import pandas as pd
import sqlite3
from pathlib import Path

DB_PATH = Path("data/guru.db")
RAW_PATH = Path("data/raw")

DECADES = ["70s", "80s", "90s", "00s", "10s", "20s"]


def load_rankings_for_tour(tour_folder, gender):
    dfs = []

    for decade in DECADES:
        file_path = RAW_PATH / tour_folder / f"{tour_folder.split('_')[1]}_rankings_{decade}.csv"

        if file_path.exists():
            print(f"Loading {file_path.name}...")
            df = pd.read_csv(file_path)

            df["ranking_date"] = pd.to_datetime(df["ranking_date"], format="%Y%m%d")
            df["gender"] = gender

            dfs.append(df[["player", "ranking_date", "rank", "points", "gender"]])

    return pd.concat(dfs, ignore_index=True)


def main():
    conn = sqlite3.connect(DB_PATH)

    # ---------------- ATP ----------------
    print("Loading ATP rankings...")
    atp_df = load_rankings_for_tour("tennis_atp", "ATP")
    atp_df.rename(columns={"player": "player_id"}, inplace=True)

    print("ATP rows before dedup:", len(atp_df))
    atp_df = atp_df.drop_duplicates(
        subset=["player_id", "ranking_date", "gender"]
    )
    print("ATP rows after dedup:", len(atp_df))

    atp_df.to_sql("rankings", conn, if_exists="append", index=False)

    # ---------------- WTA ----------------
    print("Loading WTA rankings...")
    wta_df = load_rankings_for_tour("tennis_wta", "WTA")
    wta_df.rename(columns={"player": "player_id"}, inplace=True)

    print("WTA rows before dedup:", len(wta_df))
    wta_df = wta_df.drop_duplicates(
        subset=["player_id", "ranking_date", "gender"]
    )
    print("WTA rows after dedup:", len(wta_df))

    wta_df.to_sql("rankings", conn, if_exists="append", index=False)

    conn.close()

    print("Rankings loaded successfully.")
    print(f"Total ATP rows: {len(atp_df)}")
    print(f"Total WTA rows: {len(wta_df)}")


if __name__ == "__main__":
    main()
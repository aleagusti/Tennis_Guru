import pandas as pd
import sqlite3
from pathlib import Path

DB_PATH = Path("data/guru.db")
RAW_PATH = Path("data/raw")


def load_players_for_tour(tour_folder, gender):
    file_path = RAW_PATH / tour_folder / f"{tour_folder.split('_')[1]}_players.csv"

    print(f"Loading {file_path.name}...")

    # Jeff columns:
    # player_id, name_first, name_last, hand, birth_date, ioc, height, ...
    df = pd.read_csv(file_path, low_memory=False)

    # Normalize possible column name variations
    if "name_first" in df.columns:
        df = df.rename(columns={"name_first": "first_name"})
    if "name_last" in df.columns:
        df = df.rename(columns={"name_last": "last_name"})
    if "birth_date" in df.columns:
        df = df.rename(columns={"birth_date": "dob"})
    if "ioc" in df.columns:
        df = df.rename(columns={"ioc": "country"})

    df["gender"] = gender

    # Convert birth date
    df["dob"] = pd.to_datetime(df["dob"], format="%Y%m%d", errors="coerce")

    return df[
        [
            "player_id",
            "first_name",
            "last_name",
            "gender",
            "hand",
            "dob",
            "country",
            "height",
        ]
    ]


def main():
    conn = sqlite3.connect(DB_PATH)

    # ATP
    atp_df = load_players_for_tour("tennis_atp", "ATP")
    atp_df = atp_df.drop_duplicates(subset=["player_id", "gender"])
    atp_df.to_sql("players", conn, if_exists="append", index=False)

    # WTA
    wta_df = load_players_for_tour("tennis_wta", "WTA")
    wta_df = wta_df.drop_duplicates(subset=["player_id", "gender"])
    wta_df.to_sql("players", conn, if_exists="append", index=False)

    conn.close()

    print("Players loaded successfully.")
    print(f"ATP players: {len(atp_df)}")
    print(f"WTA players: {len(wta_df)}")


if __name__ == "__main__":
    main()
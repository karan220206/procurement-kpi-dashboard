"""
Load the raw CSVs into the stg_* staging tables, unchanged (blank cells become NULL).

Run sql/01_schema.sql first, then from the project root:
    .venv/Scripts/python src/load_raw.py
"""
from sqlalchemy import text

from db import get_engine
from utils import RAW_TABLES, read_raw


def main():
    engine = get_engine()
    print(f"{'table':<22}{'CSV rows':>10}{'DB rows':>10}  status")
    for name in RAW_TABLES:
        df = read_raw(name)
        df.insert(0, "src_row", range(2, len(df) + 2))  # line 1 of the CSV is the header
        df = df.replace("", None)

        table = f"stg_{name}"
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE TABLE {table}"))
        df.to_sql(table, engine, if_exists="append", index=False, chunksize=5000)

        with engine.connect() as conn:
            db_rows = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        print(f"{table:<22}{len(df):>10,}{db_rows:>10,}  {'OK' if db_rows == len(df) else 'MISMATCH'}")


if __name__ == "__main__":
    main()

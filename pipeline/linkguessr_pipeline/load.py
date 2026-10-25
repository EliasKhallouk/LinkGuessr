"""Charge les tables finales (parquet) dans Postgres, sans interruption de service.

Tout est chargé dans le schéma « staging », indexé, puis échangé avec « graph »
dans une seule transaction : l'API ne voit jamais une base à moitié chargée.
"""
import os
from pathlib import Path

import polars as pl
import psycopg
from tqdm import tqdm

TABLES = ["person", "ref", "fact", "text_link", "relation", "edge"]
SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def _copy(cur, table: str, df: pl.DataFrame, columns: list[str]) -> None:
    cols = ", ".join(columns)
    with cur.copy(f"COPY {table} ({cols}) FROM STDIN") as copy:
        for row in tqdm(df.select(columns).iter_rows(), total=df.height, desc=table, unit=" lignes", unit_scale=True):
            copy.write_row(row)


def load(final_dir: Path, dsn: str | None = None) -> None:
    dsn = dsn or os.environ["DATABASE_URL"]
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS staging CASCADE; CREATE SCHEMA staging;")
        cur.execute("SET search_path = staging, public;")
        cur.execute((SQL_DIR / "graph_schema.sql").read_text(encoding="utf-8"))

        for table in TABLES:
            df = pl.read_parquet(final_dir / f"{table}.parquet")
            cur.execute("SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'staging' AND table_name = %s ORDER BY ordinal_position", (table,))
            columns = [c for (c,) in cur.fetchall() if c in df.columns]
            _copy(cur, table, df, columns)

        print("index...")
        cur.execute((SQL_DIR / "graph_indexes.sql").read_text(encoding="utf-8"))
        cur.execute("""
            DROP SCHEMA IF EXISTS graph_old CASCADE;
            DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'graph') THEN
                    ALTER SCHEMA graph RENAME TO graph_old;
                END IF;
            END $$;
            ALTER SCHEMA staging RENAME TO graph;
            DROP SCHEMA IF EXISTS graph_old CASCADE;
        """)
    print("chargement terminé : schéma graph à jour")

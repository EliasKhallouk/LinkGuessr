"""Charge les tables finales (parquet) dans Postgres, sans interruption de service.

Tout est chargé dans le schéma « staging », indexé, puis échangé avec « graph »
dans une seule transaction : l'API ne voit jamais une base à moitié chargée.
"""
import os
from pathlib import Path

import psycopg
import pyarrow.parquet as pq
from tqdm import tqdm

from .check import check_final

TABLES = ["person", "ref", "fact", "text_link", "relation", "edge"]
BATCH = 50_000
SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def _copy(cur, table: str, path: Path, columns: list[str]) -> None:
    """COPY par lots de BATCH lignes : la RAM reste bornée même pour les grosses tables."""
    parquet = pq.ParquetFile(path)
    with cur.copy(f"COPY {table} ({', '.join(columns)}) FROM STDIN") as copy, tqdm(
        total=parquet.metadata.num_rows, desc=table, unit=" lignes", unit_scale=True
    ) as bar:
        for batch in parquet.iter_batches(batch_size=BATCH, columns=columns):
            rows = batch.to_pydict()
            for row in zip(*(rows[c] for c in columns)):
                copy.write_row(row)
            bar.update(batch.num_rows)


def load(final_dir: Path, dsn: str | None = None) -> None:
    if not check_final(final_dir):
        raise SystemExit("tables non conformes : chargement annulé")
    dsn = dsn or os.environ["DATABASE_URL"]
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS staging CASCADE; CREATE SCHEMA staging;")
        cur.execute("SET search_path = staging, public;")
        cur.execute((SQL_DIR / "graph_schema.sql").read_text(encoding="utf-8"))

        for table in TABLES:
            path = final_dir / f"{table}.parquet"
            available = set(pq.read_schema(path).names)
            cur.execute("SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'staging' AND table_name = %s ORDER BY ordinal_position", (table,))
            columns = [c for (c,) in cur.fetchall() if c in available]
            _copy(cur, table, path, columns)

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

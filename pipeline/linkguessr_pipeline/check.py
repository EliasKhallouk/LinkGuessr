"""Vérifie les tables finales contre les contraintes de Postgres avant de les envoyer sur la VM."""
import re
from pathlib import Path

import polars as pl

SQL_SCHEMA = Path(__file__).resolve().parents[1] / "sql" / "graph_schema.sql"
LIMITS = {"smallint": 2**15 - 1, "integer": 2**31 - 1}


def _schema() -> dict[str, dict[str, str]]:
    """Colonnes et types par table, lus dans graph_schema.sql."""
    tables, current = {}, None
    for line in SQL_SCHEMA.read_text(encoding="utf-8").splitlines():
        if m := re.match(r"CREATE TABLE (\w+)", line):
            current = tables[m.group(1)] = {}
        elif current is not None and (m := re.match(r"\s+(\w+)\s+([a-z]+(?:\[\])?)", line)) and m.group(1) != "PRIMARY":
            current[m.group(1)] = m.group(2) + (" NOT NULL" if "NOT NULL" in line else "")
    return tables


def check_final(final_dir: Path) -> bool:
    ok = True
    for table, columns in _schema().items():
        frame = pl.scan_parquet(final_dir / f"{table}.parquet")
        present = set(frame.collect_schema().names())
        for col, sqltype in columns.items():
            if col not in present:
                continue
            base = sqltype.split()[0]
            problems = []
            if "NOT NULL" in sqltype and (n := frame.select(pl.col(col).is_null().sum()).collect().item()):
                problems.append(f"{n} valeurs nulles")
            if base in LIMITS:
                lo, hi = frame.select(pl.col(col).min().alias("lo"), pl.col(col).max().alias("hi")).collect().row(0)
                if lo is not None and (lo < -LIMITS[base] - 1 or hi > LIMITS[base]):
                    problems.append(f"hors limites {base} ({lo} … {hi})")
            if base == "date":
                n = frame.filter(pl.col(col).is_not_null() & pl.col(col).str.to_date(strict=False).is_null()) \
                    .select(pl.len()).collect().item()
                if n:
                    problems.append(f"{n} dates invalides")
            if problems:
                ok = False
                print(f"  ❌ {table}.{col} : {', '.join(problems)}")
    print("  ✅ tables conformes au schéma" if ok else "  ❌ corriger avant lg load")
    return ok

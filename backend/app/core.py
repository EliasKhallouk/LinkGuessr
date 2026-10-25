"""État partagé de l'API : connexions Postgres et graphe en mémoire."""
import re
from pathlib import Path

import numpy as np
from fastapi import HTTPException
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import DATABASE_URL, GRAPH_FILE
from .graph import PersonGraph

pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=5, open=False,
                      kwargs={"options": "-c search_path=graph,public", "row_factory": dict_row})
state: dict = {}

QID = re.compile(r"^Q\d+$")
PERSON_SUMMARY = ["id", "qid", "title", "name", "description", "image", "primary_domain",
                  "birth_year", "death_year", "gender", "popularity", "degree"]
APP_SCHEMA = Path(__file__).resolve().parents[1] / "sql" / "app_schema.sql"


def person_columns(alias: str = "") -> str:
    prefix = f"{alias}." if alias else ""
    return ", ".join(prefix + c for c in PERSON_SUMMARY)


def startup() -> None:
    pool.open()
    with pool.connection() as conn:
        conn.execute(APP_SCHEMA.read_text(encoding="utf-8"))
    z = np.load(GRAPH_FILE)
    state["qid_num"] = z["qid_num"]
    state["domain"] = z["domain"]
    state["domain_names"] = [str(d) for d in z["domain_names"]]
    state["dump_date"] = str(z["dump_date"]) if "dump_date" in z.files else None
    state["graph"] = PersonGraph(len(z["qid_num"]), z["a"], z["b"], z["kinds"], z["popularity"])
    state["n_edges"] = int(len(z["a"]))


def id_of(qid: str) -> int:
    if not QID.match(qid):
        raise HTTPException(400, f"QID invalide : {qid}")
    qid_num = state["qid_num"]
    i = int(np.searchsorted(qid_num, int(qid[1:])))
    if i >= len(qid_num) or qid_num[i] != int(qid[1:]):
        raise HTTPException(404, f"Personne inconnue : {qid}")
    return i


def summaries(ids: list[int]) -> dict[int, dict]:
    with pool.connection() as conn:
        rows = conn.execute(f"SELECT {person_columns()} FROM person WHERE id = ANY(%s)", (ids,)).fetchall()
    return {r["id"]: r for r in rows}

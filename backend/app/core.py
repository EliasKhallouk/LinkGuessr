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
    # Rang de chaque personne par nombre de liens (1 = la plus connectée), calculé une fois :
    # le compter en SQL à chaque fiche parcourait des centaines de milliers de lignes.
    degree = np.diff(state["graph"].csr["all"].indptr)
    state["degree_rank"] = np.searchsorted(np.sort(-degree), -degree, side="left") + 1
    pop = state["graph"].popularity
    state["pop_rank"] = np.searchsorted(np.sort(-pop), -pop, side="left") + 1  # 1 = la plus populaire


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


def path_details(res) -> dict:
    """Chemins (PathResult) -> personnes, chemins en QID et explication de chaque lien."""
    ids = sorted({v for p in res.paths for v in p})
    pairs = sorted({(min(u, v), max(u, v)) for p in res.paths for u, v in zip(p, p[1:])})
    a, b = [x for x, _ in pairs], [y for _, y in pairs]
    with pool.connection() as conn:
        text = conn.execute(
            """SELECT t.source_id, t.target_id, t.mentions, t.in_lead, t.in_infobox, t.snippet
               FROM text_link t
               JOIN unnest(%s::int[], %s::int[]) AS p(a, b)
                 ON (t.source_id = p.a AND t.target_id = p.b) OR (t.source_id = p.b AND t.target_id = p.a)""",
            (a, b),
        ).fetchall()
        rels = conn.execute(
            """SELECT r.source_id, r.target_id, r.label, r.family, r.start_year, ref.label AS context
               FROM relation r LEFT JOIN ref ON ref.qid = r.context_qid
               JOIN unnest(%s::int[], %s::int[]) AS p(a, b)
                 ON (r.source_id = p.a AND r.target_id = p.b) OR (r.source_id = p.b AND r.target_id = p.a)""",
            (a, b),
        ).fetchall()
    people = summaries(ids)
    # Pour chaque lien du chemin : les phrases qui citent l'autre personne et les relations Wikidata.
    hops = {
        f"{people[x]['qid']}-{people[y]['qid']}": {
            "text": [r for r in text if {r["source_id"], r["target_id"]} == {x, y}],
            "relations": [r for r in rels if {r["source_id"], r["target_id"]} == {x, y}],
        }
        for x, y in pairs
    }
    return {
        "length": res.length,
        "n_paths": res.n_paths,
        "paths": [[people[v]["qid"] for v in p] for p in res.paths],
        "persons": {people[v]["qid"]: people[v] for v in ids},
        "hops": hops,
    }

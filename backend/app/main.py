"""API LinkGuessr.

Le graphe (graph.npz, produit par le pipeline) est chargé en mémoire au démarrage ;
les fiches, extraits et métadonnées viennent de Postgres (schéma graph).
"""
import random
import re
from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import CORS_ORIGINS, DATABASE_URL, GRAPH_FILE
from .graph import MODES, PersonGraph
from .text import normalize

pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=5, open=False,
                      kwargs={"options": "-c search_path=graph,public", "row_factory": dict_row})
state: dict = {}

QID = re.compile(r"^Q\d+$")
PERSON_SUMMARY = """id, qid, title, name, description, image, primary_domain, birth_year, death_year,
                    gender, popularity, degree"""
DIFFICULTY_TOP = {"facile": 0.02, "moyen": 0.10, "difficile": 0.40}


def load_graph() -> None:
    z = np.load(GRAPH_FILE)
    state["qid_num"] = z["qid_num"]
    state["domain"] = z["domain"]
    state["domain_names"] = [str(d) for d in z["domain_names"]]
    state["graph"] = PersonGraph(len(z["qid_num"]), z["a"], z["b"], z["kinds"], z["popularity"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool.open()
    load_graph()
    yield
    pool.close()


app = FastAPI(title="LinkGuessr API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["GET", "POST"], allow_headers=["*"])


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
        rows = conn.execute(f"SELECT {PERSON_SUMMARY} FROM person WHERE id = ANY(%s)", (ids,)).fetchall()
    return {r["id"]: r for r in rows}


@app.get("/health")
def health():
    return {"ok": True, "persons": int(state["graph"].n)}


@app.get("/search")
def search(q: str = Query(..., min_length=1, max_length=80), limit: int = Query(8, ge=1, le=30)):
    """Autocomplétion : tous les mots doivent apparaître ; les noms qui commencent par la saisie
    et les personnes les plus connues d'abord. Recherche approchée si rien ne correspond."""
    norm = normalize(q).strip()
    tokens = [t for t in re.split(r"\s+", norm) if t]
    if not tokens:
        return {"results": []}
    where = " AND ".join(["search_text LIKE %s"] * len(tokens))
    params = [f"%{t}%" for t in tokens]
    with pool.connection() as conn:
        rows = conn.execute(
            f"""SELECT {PERSON_SUMMARY} FROM person WHERE {where}
                ORDER BY (search_text LIKE %s) DESC, popularity DESC LIMIT %s""",
            (*params, f"{norm}%", limit),
        ).fetchall()
        if not rows:
            rows = conn.execute(
                f"""SELECT {PERSON_SUMMARY} FROM person WHERE %s <%% search_text
                    ORDER BY word_similarity(%s, search_text) DESC, popularity DESC LIMIT %s""",
                (norm, norm, limit),
            ).fetchall()
    return {"results": rows}


@app.get("/person/{qid}")
def person(qid: str):
    pid = id_of(qid)
    with pool.connection() as conn:
        p = conn.execute("SELECT * FROM person WHERE id = %s", (pid,)).fetchone()
        ref_qids = [q for q in (p["birth_place"], p["birth_country"], p["death_place"], p["death_country"]) if q]
        ref_qids += (p["citizenships"] or []) + (p["occupations"] or [])
        labels = {r["qid"]: r["label"] for r in conn.execute(
            "SELECT qid, label FROM ref WHERE qid = ANY(%s)", (ref_qids,)).fetchall()}
        facts = conn.execute(
            """SELECT f.prop, f.value_qid, r.label, f.start_year, f.end_year, f.start_date, f.end_date, f.qualifiers
               FROM fact f LEFT JOIN ref r ON r.qid = f.value_qid
               WHERE f.person_id = %s ORDER BY f.prop, f.start_year NULLS LAST""",
            (pid,),
        ).fetchall()
        relations = conn.execute(
            f"""SELECT rel.label AS relation, rel.family, rel.start_year, rel.end_year, ref.label AS context,
                       o.qid, o.name, o.image
                FROM relation rel JOIN person o ON o.id = rel.target_id
                LEFT JOIN ref ON ref.qid = rel.context_qid
                WHERE rel.source_id = %s ORDER BY rel.family, o.popularity DESC""",
            (pid,),
        ).fetchall()
        cites = conn.execute(
            """SELECT o.qid, o.name, o.image, t.mentions, t.in_lead, t.in_infobox, t.sections, t.snippet
               FROM text_link t JOIN person o ON o.id = t.target_id
               WHERE t.source_id = %s ORDER BY t.in_lead DESC, t.mentions DESC LIMIT 40""",
            (pid,),
        ).fetchall()
        cited_by = conn.execute(
            """SELECT o.qid, o.name, o.image, t.mentions, t.snippet
               FROM text_link t JOIN person o ON o.id = t.source_id
               WHERE t.target_id = %s ORDER BY o.popularity DESC LIMIT 40""",
            (pid,),
        ).fetchall()
    return {"person": p, "labels": labels, "facts": facts, "relations": relations,
            "cites": cites, "cited_by": cited_by}


@app.get("/path")
def path(
    source: str = Query(..., alias="from"),
    target: str = Query(..., alias="to"),
    mode: str = Query("all", pattern=f"^({'|'.join(MODES)})$"),
    limit: int = Query(5, ge=1, le=20),
):
    """Plus courts chemins entre deux personnes, avec l'explication de chaque lien."""
    s, t = id_of(source), id_of(target)
    res = state["graph"].shortest_paths(s, t, mode=mode, limit=limit)
    if res.length is None:
        return {"length": None, "n_paths": 0, "paths": [], "persons": {}, "hops": []}

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


@app.get("/neighbors/{qid}")
def neighbors(qid: str, limit: int = Query(50, ge=1, le=500)):
    pid = id_of(qid)
    with pool.connection() as conn:
        rows = conn.execute(
            f"""SELECT {', '.join('o.' + c.strip() for c in PERSON_SUMMARY.split(','))}, e.kinds, e.mentions, e.weight
                FROM edge e JOIN person o ON o.id = CASE WHEN e.a = %s THEN e.b ELSE e.a END
                WHERE e.a = %s OR e.b = %s
                ORDER BY e.weight DESC, o.popularity DESC LIMIT %s""",
            (pid, pid, pid, limit),
        ).fetchall()
    return {"results": rows}


@app.get("/random_pair")
def random_pair(
    difficulty: str = Query("moyen", pattern="^(facile|moyen|difficile)$"),
    domain: str | None = None,
    mode: str = Query("all", pattern=f"^({'|'.join(MODES)})$"),
    min_length: int = Query(2, ge=1, le=8),
    max_length: int = Query(6, ge=1, le=12),
):
    """Deux personnes tirées parmi les plus connues (selon la difficulté), reliées par un chemin
    de longueur comprise entre min_length et max_length."""
    graph = state["graph"]
    pop = graph.popularity
    candidates = np.flatnonzero(pop >= np.quantile(pop, 1 - DIFFICULTY_TOP[difficulty]))
    if domain:
        if domain not in state["domain_names"]:
            raise HTTPException(400, f"Domaine inconnu. Domaines : {state['domain_names']}")
        candidates = candidates[state["domain"][candidates] == state["domain_names"].index(domain)]
    if len(candidates) < 2:
        raise HTTPException(404, "Pas assez de personnes pour ces critères")
    rng = random.Random()
    for _ in range(50):
        s, t = (int(x) for x in rng.sample(candidates.tolist(), 2))
        res = graph.shortest_paths(s, t, mode=mode, limit=1)
        if res.length is not None and min_length <= res.length <= max_length:
            people = summaries([s, t])
            return {"from": people[s], "to": people[t], "length": res.length, "n_paths": res.n_paths}
    raise HTTPException(404, "Aucune paire trouvée, élargir les critères")

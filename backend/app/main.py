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

from . import game
from .config import CORS_ORIGIN_REGEX, CORS_ORIGINS
from .core import id_of, person_columns, pool, startup, state, summaries
from .graph import MODES
from .text import normalize

# Part des plus populaires où l'on tire les personnes. Sur 765 000 personnes : ~1 150 / ~7 600 / ~38 000.
DIFFICULTY_TOP = {"facile": 0.0015, "moyen": 0.01, "difficile": 0.05}
MIN_POOL = 200  # réservoir minimal, pour les petits domaines


@asynccontextmanager
async def lifespan(app: FastAPI):
    startup()
    yield
    pool.close()


app = FastAPI(title="LinkGuessr API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_origin_regex=CORS_ORIGIN_REGEX,
                   allow_methods=["GET", "POST"], allow_headers=["*"])
app.include_router(game.router)


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
            f"""SELECT {person_columns()} FROM person WHERE {where}
                ORDER BY (search_text LIKE %s) DESC, popularity DESC LIMIT %s""",
            (*params, f"{norm}%", limit),
        ).fetchall()
        if not rows:
            rows = conn.execute(
                f"""SELECT {person_columns()} FROM person WHERE %s <%% search_text
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
            """SELECT o.qid, o.title, o.name, o.image, t.mentions, t.in_lead, t.in_infobox, t.sections, t.snippet
               FROM text_link t JOIN person o ON o.id = t.target_id
               WHERE t.source_id = %s ORDER BY t.in_lead DESC, t.mentions DESC LIMIT 40""",
            (pid,),
        ).fetchall()
        cited_by = conn.execute(
            """SELECT o.qid, o.title, o.name, o.image, t.mentions, t.snippet
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
    track: bool = False,
):
    """Plus courts chemins entre deux personnes, avec l'explication de chaque lien.
    track=true : compte la paire dans les « paires les plus demandées » (explorateur uniquement)."""
    s, t = id_of(source), id_of(target)
    if track and s != t:
        game.record_path_request(source, target)
    res = state["graph"].shortest_paths(s, t, mode=mode, limit=limit)
    if res.length is None:
        return {"length": None, "n_paths": 0, "paths": [], "persons": {}, "hops": {}}
    return path_details(res)


def path_details(res) -> dict:

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
            f"""SELECT {person_columns('o')}, e.kinds, e.mentions, e.weight
                FROM edge e JOIN person o ON o.id = CASE WHEN e.a = %s THEN e.b ELSE e.a END
                WHERE e.a = %s OR e.b = %s
                ORDER BY e.weight DESC, o.popularity DESC LIMIT %s""",
            (pid, pid, pid, limit),
        ).fetchall()
    return {"results": rows}


def _candidates(difficulty: str, domain: str | None) -> np.ndarray:
    """Les personnes les plus connues (part DIFFICULTY_TOP du domaine), au moins MIN_POOL si possible."""
    pop = state["graph"].popularity
    pool_ids = np.arange(len(pop))
    if domain:
        if domain not in state["domain_names"]:
            raise HTTPException(400, f"Domaine inconnu. Domaines : {state['domain_names']}")
        pool_ids = pool_ids[state["domain"] == state["domain_names"].index(domain)]
    k = min(len(pool_ids), max(MIN_POOL, int(len(pool_ids) * DIFFICULTY_TOP[difficulty])))
    if k < 2:
        raise HTTPException(404, "Pas assez de personnes pour ces critères")
    return pool_ids[np.argpartition(-pop[pool_ids], k - 1)[:k]]


def _pick_pair(difficulty: str, domain: str | None, mode: str, min_length: int, max_length: int, limit: int = 1):
    """Deux personnes tirées parmi les plus connues, reliées par un chemin de longueur voulue."""
    graph, candidates, rng = state["graph"], _candidates(difficulty, domain), np.random.default_rng()
    for _ in range(50):
        s, t = (int(x) for x in rng.choice(candidates, 2, replace=False))
        res = graph.shortest_paths(s, t, mode=mode, limit=limit)
        if res.length is not None and min_length <= res.length <= max_length:
            return s, t, res
    raise HTTPException(404, "Aucune paire trouvée, élargir les critères")


@app.get("/random_pair")
def random_pair(
    difficulty: str = Query("moyen", pattern="^(facile|moyen|difficile)$"),
    domain: str | None = None,
    mode: str = Query("all", pattern=f"^({'|'.join(MODES)})$"),
    min_length: int = Query(2, ge=1, le=8),
    max_length: int = Query(6, ge=1, le=12),
):
    """Deux personnes connues (selon la difficulté) et la longueur du plus court chemin.
    Le chemin lui-même n'est pas renvoyé : le joueur le demande à /path après avoir répondu."""
    s, t, res = _pick_pair(difficulty, domain, mode, min_length, max_length)
    people = summaries([s, t])
    return {"from": people[s], "to": people[t], "length": res.length, "n_paths": res.n_paths}


@app.get("/random_path")
def random_path(
    difficulty: str = Query("moyen", pattern="^(facile|moyen|difficile)$"),
    domain: str | None = None,
    min_length: int = Query(2, ge=2, le=8),
    max_length: int = Query(5, ge=2, le=12),
):
    """« Qui est caché ? » : un plus court chemin dont une personne intermédiaire est à deviner.
    Les indices (domaine, dates, initiales) sont donnés ; le nom reste dans `answer`."""
    _, _, res = _pick_pair(difficulty, domain, "all", min_length, max_length)
    details = path_details(res)
    chain = details["paths"][0]
    masked = random.randint(1, len(chain) - 2)
    answer = details["persons"][chain[masked]]
    hops = {k: v for k, v in details["hops"].items() if chain[masked] not in k.split("-")}
    return {
        "path": chain,
        "masked_index": masked,
        "persons": {q: p for q, p in details["persons"].items() if q in chain and q != answer["qid"]},
        "hops": hops,
        "answer": answer,
        "hints": {
            "domain": answer["primary_domain"],
            "birth_year": answer["birth_year"],
            "death_year": answer["death_year"],
            "initials": "".join(w[0] for w in re.split(r"[\s-]+", answer["name"]) if w),
            "name_length": len(answer["name"]),
        },
    }


TOP_ORDER = {"popularity": "popularity", "degree": "degree", "pageviews": "pageviews_12m", "pagerank": "pagerank"}


@app.get("/top")
def top(
    by: str = Query("popularity", pattern=f"^({'|'.join(TOP_ORDER)})$"),
    domain: str | None = None,
    limit: int = Query(10, ge=1, le=100),
):
    where, params = ("WHERE primary_domain = %s", [domain]) if domain else ("", [])
    with pool.connection() as conn:
        rows = conn.execute(
            f"""SELECT {person_columns()}, pageviews_12m, pagerank FROM person {where}
                ORDER BY {TOP_ORDER[by]} DESC NULLS LAST LIMIT %s""",
            (*params, limit),
        ).fetchall()
    return {"by": by, "results": rows}


@app.get("/domains")
def domains():
    return {"results": state["domain_names"]}

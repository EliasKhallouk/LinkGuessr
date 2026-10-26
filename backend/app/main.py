"""API LinkGuessr.

Le graphe (graph.npz, produit par le pipeline) est chargé en mémoire au démarrage ;
les fiches, extraits et métadonnées viennent de Postgres (schéma graph).
"""
import random
import re
from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware

from . import admin, daily, game, seo
from .clues import clues
from .config import CORS_ORIGIN_REGEX, CORS_ORIGINS
from .core import id_of, path_details, person_columns, pool, startup, state, summaries
from .graph import MODES, PathResult
from .policy import http_policy
from .text import normalize

# Niveaux de difficulté (calés sur les rangs de popularité, sur 765 000 personnes) :
# - top : on tire les personnes parmi les N plus populaires (rang 200 : Ronaldinho, Cléopâtre ;
#   800 : Jennifer Lawrence ; 3 000 : Eddie Redmayne ; 12 000 : Kevin Mitnick ; 60 000 : quasi inconnus) ;
# - hidden : « Qui est caché ? », rangs de popularité permis pour la personne à deviner (None : sans limite) ;
#   dans les niveaux durs on écarte les stars, sinon les chemins passent toujours par Trump ou Napoléon ;
# - hidden_length, hidden_mode : longueur du chemin de « Qui est caché ? » et type de liens (forts en
#   facile et moyen : les liens sont évidents, « Zidane → ? → Benzema ») ;
# - choices : en facile, on répond en choisissant parmi 4 personnes.
LEVELS = {
    "facile": {"top": 200, "hidden": (1, 300), "hidden_length": (2, 2), "hidden_mode": "strong", "choices": 4},
    "moyen": {"top": 800, "hidden": (1, 2_000), "hidden_length": (2, 3), "hidden_mode": "strong"},
    "difficile": {"top": 3_000, "hidden": (200, 8_000), "hidden_length": (2, 3)},
    "extreme": {"top": 12_000, "hidden": (1_000, 30_000), "hidden_length": (3, 4)},
    "humain": {"top": 60_000, "hidden": (5_000, None), "hidden_length": (4, 6)},
}
CHOICES_TOP = 600  # les mauvaises propositions du choix multiple : parmi les 600 plus connus, même domaine
LEVEL = f"^({'|'.join(LEVELS)})$"
MIN_POOL = 200  # réservoir minimal, pour les petits domaines


@asynccontextmanager
async def lifespan(app: FastAPI):
    startup()
    yield
    pool.close()


app = FastAPI(title="LinkGuessr API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_origin_regex=CORS_ORIGIN_REGEX,
                   allow_methods=["GET", "POST"], allow_headers=["*"])
app.middleware("http")(http_policy)
app.include_router(game.router)
app.include_router(daily.router)
app.include_router(daily.admin_router)
app.include_router(admin.router)
app.include_router(seo.router)


@app.get("/health")
def health():
    return {"ok": True, "persons": int(state["graph"].n)}


@app.get("/search")
def search(q: str = Query(..., min_length=1, max_length=80), limit: int = Query(8, ge=1, le=30)):
    """Autocomplétion : tous les mots tapés doivent apparaître (index trigramme).
    Classement : d'abord quand chaque mot tapé est un début de mot du nom (« zidane » → Zinédine
    Zidane plutôt qu'un nom qui contient « zidane » au milieu), puis les plus connus.
    Recherche approchée si rien ne correspond."""
    norm = normalize(q).strip()
    tokens = [t for t in re.split(r"\s+", norm) if t]
    if not tokens:
        return {"results": []}
    with pool.connection() as conn:
        if len(norm) < 3:
            # Trop court pour l'index trigramme : on cherche les noms qui commencent par la saisie.
            rows = conn.execute(
                f"""SELECT {person_columns()} FROM person WHERE search_text LIKE %s
                    ORDER BY popularity DESC LIMIT %s""",
                (f"{norm}%", limit),
            ).fetchall()
            return {"results": rows}
        where = " AND ".join(["search_text LIKE %s"] * len(tokens))
        word_start = " AND ".join(["search_text ~ %s"] * len(tokens))
        rows = conn.execute(
            f"""SELECT {person_columns()} FROM person WHERE {where}
                ORDER BY ({word_start}) DESC, popularity DESC LIMIT %s""",
            (*[f"%{t}%" for t in tokens], *[r"\m" + re.escape(t) for t in tokens], limit),
        ).fetchall()
        if not rows:
            # Fautes de frappe (« einstien ») : similarité de trigrammes, seuil plus tolérant que 0,6.
            conn.execute("SELECT set_config('pg_trgm.word_similarity_threshold', '0.45', true)")
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


@app.get("/person/{qid}/card")
def person_card(qid: str, response: Response):
    """Version légère d'une fiche pour les aperçus de partage et le référencement :
    résumé, position dans le réseau et personnes les plus proches (liens les plus forts)."""
    pid = id_of(qid)
    with pool.connection() as conn:
        p = conn.execute(
            f"""SELECT {person_columns()}, pageviews_12m, sitelinks, community FROM person WHERE id = %s""",
            (pid,),
        ).fetchone()
        closest = conn.execute(
            f"""SELECT {person_columns('o')}, e.weight FROM edge e
                JOIN person o ON o.id = CASE WHEN e.a = %s THEN e.b ELSE e.a END
                WHERE e.a = %s OR e.b = %s ORDER BY e.weight DESC, o.popularity DESC LIMIT 5""",
            (pid, pid, pid),
        ).fetchall()
    p["degree_rank"] = int(state["degree_rank"][pid])
    p["total"] = int(state["graph"].n)
    response.headers["Cache-Control"] = "public, max-age=3600, s-maxage=86400"
    return {"person": p, "closest": closest}


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
    """Les personnes les plus connues (même part que LEVELS[…]["top"] sur tout le graphe, appliquée au domaine),
    au moins MIN_POOL si possible."""
    pop = state["graph"].popularity
    pool_ids = np.arange(len(pop))
    if domain:
        if domain not in state["domain_names"]:
            raise HTTPException(400, f"Domaine inconnu. Domaines : {state['domain_names']}")
        pool_ids = pool_ids[state["domain"] == state["domain_names"].index(domain)]
    share = LEVELS[difficulty]["top"] / len(pop)
    k = min(len(pool_ids), max(MIN_POOL, int(len(pool_ids) * share)))
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


def _pick_hidden(difficulty: str, domain: str | None, min_length: int, max_length: int) -> tuple[list[int], int]:
    """Un plus court chemin et la position de la personne à deviner, assez connue pour le niveau."""
    (lo, hi), rank = LEVELS[difficulty]["hidden"], state["pop_rank"]
    mode = LEVELS[difficulty].get("hidden_mode", "all")
    for _ in range(30):
        _, _, res = _pick_pair(difficulty, domain, mode, min_length, max_length, limit=20)
        choices = [(p, i) for p in res.paths for i in range(1, len(p) - 1)
                   if rank[p[i]] >= lo and (hi is None or rank[p[i]] <= hi)]
        if choices:
            return random.choice(choices)
    raise HTTPException(404, "Aucun chemin trouvé pour ce niveau, réessayez")


def _valid_middles(before: int, after: int) -> set[int]:
    """Toutes les personnes liées à la fois à `before` et à `after` : chacune est une bonne réponse."""
    csr = state["graph"].csr["all"]
    return set(csr.neighbors_of(before).tolist()) & set(csr.neighbors_of(after).tolist())


def _wrong_choices(answer: int, chain: list[int], valid: set[int], n: int, rng: random.Random) -> list[int]:
    """Mauvaises propositions plausibles : très connues, du même domaine, mais pas des bonnes réponses."""
    pop, dom = state["graph"].popularity, state["domain"]
    top = np.argpartition(-pop, CHOICES_TOP)[:CHOICES_TOP].tolist()
    allowed = [i for i in top if i not in valid and i not in chain]
    same = [i for i in allowed if dom[i] == dom[answer]]
    picked = rng.sample(same, min(n, len(same)))
    return picked + rng.sample([i for i in allowed if i not in picked], n - len(picked))


def _pick_balanced(difficulty: str, domain: str | None, mode: str, min_length: int, max_length: int):
    """Comme _pick_pair, mais la longueur visée est tirée à parts égales entre min et max : sinon presque
    toutes les paires sont à 2 ou 3 liens et répondre toujours le même chiffre suffit.
    Si la longueur visée est trop rare, on garde la paire trouvée la plus proche."""
    graph, candidates, rng = state["graph"], _candidates(difficulty, domain), np.random.default_rng()
    target, best = int(rng.integers(min_length, max_length + 1)), None
    for _ in range(120):
        s, t = (int(x) for x in rng.choice(candidates, 2, replace=False))
        res = graph.shortest_paths(s, t, mode=mode, limit=1)
        if res.length is None or not min_length <= res.length <= max_length:
            continue
        if res.length == target:
            return s, t, res
        if best is None or abs(res.length - target) < abs(best[2].length - target):
            best = (s, t, res)
    if best is None:
        raise HTTPException(404, "Aucune paire trouvée, élargir les critères")
    return best


@app.get("/random_pair")
def random_pair(
    difficulty: str = Query("moyen", pattern=LEVEL),
    domain: str | None = None,
    mode: str = Query("all", pattern=f"^({'|'.join(MODES)})$"),
    min_length: int = Query(2, ge=1, le=8),
    max_length: int = Query(6, ge=1, le=12),
    balanced: bool = False,
):
    """Deux personnes connues (selon la difficulté) et la longueur du plus court chemin.
    Le chemin lui-même n'est pas renvoyé : le joueur le demande à /path après avoir répondu.
    balanced=true : longueurs réparties à parts égales (jeu « Combien de liens »)."""
    pick = _pick_balanced if balanced else _pick_pair
    s, t, res = pick(difficulty, domain, mode, min_length, max_length)
    people = summaries([s, t])
    return {"from": people[s], "to": people[t], "length": res.length, "n_paths": res.n_paths}


@app.get("/random_path/check")
def random_path_check(before: str, after: str, guess: str):
    """Une réponse autre que celle attendue est juste si elle est liée aux deux voisins de la personne cachée."""
    b, a, g = id_of(before), id_of(after), id_of(guess)
    return {"ok": g not in (a, b) and g in _valid_middles(b, a)}


@app.get("/random_path")
def random_path(
    difficulty: str = Query("moyen", pattern=LEVEL),
    domain: str | None = None,
    min_length: int | None = Query(None, ge=2, le=8),
    max_length: int | None = Query(None, ge=2, le=12),
):
    """« Qui est caché ? » : un plus court chemin dont une personne intermédiaire est à deviner.
    Les indices (domaine, dates, initiales) sont donnés ; le nom reste dans `answer`, et les liens
    de la personne cachée (phrases qui la citent) dans `answer_hops`, à afficher une fois la réponse donnée."""
    lo, hi = LEVELS[difficulty]["hidden_length"]
    ids, masked = _pick_hidden(difficulty, domain, min_length or lo, max_length or hi)
    return _puzzle(ids, masked, difficulty, random.Random())


@app.get("/random_path/replay")
def random_path_replay(
    chemin: str = Query(..., pattern=r"^Q\d+(-Q\d+){2,7}$"),
    cache: int = Query(..., ge=1),
    niveau: str = Query("moyen", pattern=LEVEL),
):
    """La même énigme qu'un ami a partagée (/defi?jeu=cache&chemin=Q1-Q2-Q3&cache=1&niveau=facile),
    avec les mêmes propositions : le tirage est fixé par le lien."""
    ids = [id_of(q) for q in chemin.split("-")]
    if cache > len(ids) - 2:
        raise HTTPException(400, "Position de la personne cachée invalide")
    csr = state["graph"].csr["all"]
    if any(b not in set(csr.neighbors_of(a).tolist()) for a, b in zip(ids, ids[1:])):
        raise HTTPException(400, "Ce chemin n'existe pas (ou plus) dans les données")
    return _puzzle(ids, cache, niveau, random.Random(f"{chemin}-{cache}-{niveau}"))


def _puzzle(ids: list[int], masked: int, difficulty: str, rng: random.Random) -> dict:
    """L'énigme : chemin, personne cachée, phrases à trou, indices et, en facile, choix multiple."""
    level = LEVELS[difficulty]
    details = path_details(PathResult(len(ids) - 1, 1, [ids]))
    chain = details["paths"][0]
    answer = details["persons"][chain[masked]]
    hidden = {k: v for k, v in details["hops"].items() if answer["qid"] in k.split("-")}
    choices = None
    if level.get("choices"):
        valid = _valid_middles(ids[masked - 1], ids[masked + 1])
        wrong = _wrong_choices(ids[masked], ids, valid, level["choices"] - 1, rng)
        people = summaries(wrong)
        choices = [people[i] for i in wrong] + [answer]
        rng.shuffle(choices)
    return {
        "difficulty": difficulty,
        "choices": choices,
        "clues": clues(hidden, answer, details["persons"]),
        "path": chain,
        "masked_index": masked,
        "persons": {q: p for q, p in details["persons"].items() if q != answer["qid"]},
        "hops": {k: v for k, v in details["hops"].items() if k not in hidden},
        "answer_hops": hidden,
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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from neo4j import GraphDatabase
import os
from fastapi.responses import JSONResponse
from fastapi import Body, Query
from pydantic import BaseModel, Field, validator
from typing import List, Optional
from pathlib import Path
import json
import time
import threading
import unicodedata
import re
import random
import difflib

from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

app = FastAPI()

# Autoriser le front-end à accéder à l'API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/graph")
def get_graph():
    query = """
    MATCH (a:Person)-[r:CONNAIT]->(b:Person)
    RETURN a.name AS from, b.name AS to
    """

    with driver.session() as session:
        result = session.run(query)
        nodes_set = set()
        edges = []

        for record in result:
            from_name = record["from"]
            to_name = record["to"]
            nodes_set.add(from_name)
            nodes_set.add(to_name)
            edges.append({"from": from_name, "to": to_name})

        nodes = [{"id": name} for name in nodes_set]
        return {"nodes": nodes, "edges": edges}

#############################
# Leaderboard persistence
#############################

LEADERBOARD_FILE = Path(os.getenv("LEADERBOARD_PATH", "backend/leaderboard.json"))
_lb_lock = threading.Lock()
MAX_ENTRIES_PER_NAME = int(os.getenv("LEADERBOARD_MAX_ENTRIES_PER_NAME", "3"))
MIN_SECONDS_BETWEEN_SUBMITS_PER_NAME = int(os.getenv("LEADERBOARD_MIN_SECONDS_BETWEEN", "10"))
NAME_MAX_LEN = int(os.getenv("LEADERBOARD_NAME_MAX_LENGTH", "16"))

# Popular pairs tracking (most requested /shortest_paths queries)
POPULAR_PAIRS_FILE = Path(os.getenv("POPULAR_PAIRS_PATH", "backend/popular_pairs.json"))
_pp_lock = threading.Lock()
POPULAR_PAIRS_RETENTION_DAYS = int(os.getenv("POPULAR_PAIRS_RETENTION_DAYS", "365"))


def _load_popular_pairs():
    if not POPULAR_PAIRS_FILE.exists():
        return {}
    try:
        data = json.loads(POPULAR_PAIRS_FILE.read_text(encoding="utf-8")) or {}
        # Normalize stored values to lists of ints (timestamps)
        normalized = {}
        for k, v in (data.items() if isinstance(data, dict) else []):
            if isinstance(v, list):
                # keep only integer timestamps
                normalized[k] = [int(x) for x in v if isinstance(x, (int, float))]
            elif isinstance(v, int):
                # legacy: a single integer count; convert to a single synthetic timestamp at file mtime
                try:
                    mtime = int(POPULAR_PAIRS_FILE.stat().st_mtime)
                except Exception:
                    mtime = int(time.time())
                normalized[k] = [mtime]
            else:
                normalized[k] = []
        return normalized
    except Exception:
        return {}


def _save_popular_pairs(d):
    POPULAR_PAIRS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = POPULAR_PAIRS_FILE.with_suffix(".json.tmp")
    # Ensure JSON serializable (list of ints)
    safe = {}
    for k, v in (d.items() if isinstance(d, dict) else []):
        if isinstance(v, list):
            safe[k] = [int(x) for x in v]
        elif isinstance(v, int):
            safe[k] = [int(v)]
        else:
            safe[k] = []
    tmp.write_text(json.dumps(safe, ensure_ascii=False), encoding="utf-8")
    tmp.replace(POPULAR_PAIRS_FILE)


class ScoreSubmission(BaseModel):
    name: str = Field(..., min_length=1, max_length=NAME_MAX_LEN)
    score: int = Field(..., ge=0)
    duration: int = Field(..., ge=1)

    @validator("name")
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Le nom ne peut pas être vide")
        return v


class ScoreEntry(ScoreSubmission):
    ts: int  # epoch seconds


def _load_leaderboard() -> List[ScoreEntry]:
    if not LEADERBOARD_FILE.exists():
        return []
    try:
        data = json.loads(LEADERBOARD_FILE.read_text(encoding="utf-8"))
        # tolerate legacy or empty file
        entries = []
        for item in data or []:
            # minimal schema validation
            if not all(k in item for k in ("name", "score", "duration", "ts")):
                continue
            entries.append(ScoreEntry(**item))
        return entries
    except Exception:
        return []


def _save_leaderboard(entries: List[ScoreEntry]) -> None:
    LEADERBOARD_FILE.parent.mkdir(parents=True, exist_ok=True)
    # write atomically
    tmp = LEADERBOARD_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps([e.dict() for e in entries], ensure_ascii=False), encoding="utf-8")
    tmp.replace(LEADERBOARD_FILE)


def _sorted(entries: List[ScoreEntry]) -> List[ScoreEntry]:
    # Higher score first; tie-breaker: shorter duration first; then most recent first
    return sorted(entries, key=lambda e: (-e.score, e.duration, -e.ts))


def _normalize_name(name: str) -> str:
    # Strip and remove emojis/unsupported chars
    s = name.strip()
    # Normalize unicode to NFKD and remove diacritics
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    # Keep only allowed chars: letters, digits, space, underscore, hyphen
    s = re.sub(r"[^A-Za-z0-9 _-]", "", s)
    # Collapse multiple spaces
    s = re.sub(r"\s+", " ", s)
    s = s.strip()
    if not s:
        s = "Anonyme"
    # Cap length strictly
    return s[:NAME_MAX_LEN]


@app.post("/submit_score")
def submit_score(payload: ScoreSubmission = Body(...)):
    now = int(time.time())
    # Sanitize name
    sanitized_name = _normalize_name(payload.name)
    entry = ScoreEntry(name=sanitized_name, score=payload.score, duration=payload.duration, ts=now)
    with _lb_lock:
        entries = _load_leaderboard()
        # Rate limit per name
        last_ts = None
        for e in entries:
            if e.name.lower() == entry.name.lower():
                if last_ts is None or e.ts > last_ts:
                    last_ts = e.ts
        if last_ts is not None and (now - last_ts) < MIN_SECONDS_BETWEEN_SUBMITS_PER_NAME:
            return JSONResponse(status_code=429, content={
                "ok": False,
                "error": f"Trop de soumissions pour ce pseudo, réessayez dans {MIN_SECONDS_BETWEEN_SUBMITS_PER_NAME - (now - last_ts)}s.",
            })

        # Append and sort
        entries.append(entry)
        entries = _sorted(entries)

        # Enforce per-name cap, keeping the best entries for each name
        kept: List[ScoreEntry] = []
        counts = {}
        for e in entries:
            key = e.name.lower()
            c = counts.get(key, 0)
            if c < MAX_ENTRIES_PER_NAME:
                kept.append(e)
                counts[key] = c + 1
        entries = kept
        _save_leaderboard(entries)

        # compute rank of this exact entry instance after capping
        rank = None
        for idx, e in enumerate(entries, start=1):
            if e.ts == entry.ts and e.name == entry.name and e.score == entry.score and e.duration == entry.duration:
                rank = idx
                break
        stored = rank is not None
        return {
            "ok": True,
            "stored": stored,
            "rank": rank,
            "total": len(entries),
            "entry": entry.dict(),
        }


@app.get("/leaderboard")
def leaderboard(limit: int = Query(10, ge=1, le=500)):
    with _lb_lock:
        entries = _sorted(_load_leaderboard())
        sliced = entries[:limit]
        return {
            "total": len(entries),
            "limit": limit,
            "entries": [
                {"rank": i + 1, **e.dict()} for i, e in enumerate(sliced)
            ],
        }

@app.get("/shortest_paths")
def shortest_paths(person1: str = Query(...), person2: str = Query(...), limit: int = Query(3)):
    if person1.strip().lower() == person2.strip().lower():
        return JSONResponse(
            status_code=400,
            content={
                "error": "Les deux personnes sont identiques.",
                "message": "Veuillez entrer deux personnes différentes."
            }
        )

    # Étape 1 : trouver la longueur minimale du plus court chemin
    min_len_query = """
    MATCH p = shortestPath((a:Person {name: $person1})-[:CONNAIT*]-(b:Person {name: $person2}))
    RETURN length(p) AS minLen
    """

    with driver.session() as session:
        result = session.run(min_len_query, person1=person1, person2=person2).single()
        if not result or result["minLen"] is None:
            return {"nb_relations": None, "chemins": []}

        min_len = result["minLen"]

        # Étape 2 : récupérer tous les chemins de cette longueur exacte
        query_all = """
        MATCH p = (a:Person {name: $person1})-[:CONNAIT*{min_len}]-(b:Person {name: $person2})
        WHERE length(p) = $min_len
        RETURN [n IN nodes(p) | n.name] AS chemin, length(p) AS nb_relations
        LIMIT $limit
        """.replace("{min_len}", str(min_len))  # ⚠️ on remplace dans la chaîne (Neo4j ne supporte pas de variable ici)

        records = session.run(query_all, person1=person1, person2=person2, min_len=min_len, limit=limit).data()

    # Log du couple (comme dans ta version d’origine)
    try:
        a = (person1 or "").strip()
        b = (person2 or "").strip()
        if a and b:
            key = "::".join(sorted([a, b], key=lambda s: s.lower()))
            ts = int(time.time())
            with _pp_lock:
                d = _load_popular_pairs()
                lst = d.get(key, [])
                if not isinstance(lst, list):
                    lst = []
                lst.append(ts)
                cutoff = ts - (POPULAR_PAIRS_RETENTION_DAYS * 86400)
                lst = [int(x) for x in lst if int(x) >= cutoff]
                d[key] = lst
                _save_popular_pairs(d)
    except Exception:
        pass

    # Format de sortie
    chemins = [{"nb_relations": r["nb_relations"], "chemin": r["chemin"]} for r in records]
    return {"min_len": min_len, "nb_chemins": len(chemins), "chemins": chemins}


@app.get("/popular_pairs")
def popular_pairs(limit: int = Query(10, ge=1, le=100), period: str = Query("7", regex="^(7|30|all)$")):
    """Retourne les paires (person1, person2) les plus demandées par nombre d'appels à /shortest_path.

    Le stockage est simple (fichier JSON) avec clé 'A::B' triée lexicographiquement pour rendre la paire commutative.
    (attention: le endpoint principal de chemins s'appelle maintenant `/shortest_paths`).
    """
    now_ts = int(time.time())
    with _pp_lock:
        d = _load_popular_pairs()
        # compute counts within the requested period
        if period == "all":
            counts = {k: len(v) for k, v in d.items()}
        else:
            days = int(period)
            cutoff = now_ts - (days * 86400)
            counts = {k: sum(1 for ts in (v or []) if int(ts) >= cutoff) for k, v in d.items()}
        items = sorted(counts.items(), key=lambda kv: -kv[1])[:limit]
        results = []
        for k, cnt in items:
            try:
                a, b = k.split("::", 1)
            except Exception:
                a, b = k, ""
            results.append({"person1": a, "person2": b, "count": int(cnt)})
    return {"results": results, "period": period}


@app.get("/challenge")
def challenge(max_retries: int = Query(5, ge=1, le=50)):
    """Retourne un défi: deux personnes aléatoires et le plus court chemin entre elles.

    Essaie jusqu'à max_retries paires pour trouver une paire connectée. En cas d'échec,
    renvoie la dernière paire tirée avec nb_relations=None.
    """
    last_pair = (None, None)
    last_res = {"nb_relations": None, "chemin": []}
    with driver.session() as session:
        for _ in range(max_retries):
            rec = session.run(
                """
                MATCH (p:Person)
                WITH p ORDER BY rand() LIMIT 2
                RETURN collect(p.name) AS names
                """
            ).single()
            if not rec:
                continue
            names = rec.get("names") or []
            if len(names) < 2:
                continue
            p1, p2 = names[0], names[1]
            if not p1 or not p2 or p1 == p2:
                continue
            last_pair = (p1, p2)
            sp = session.run(
                """
                MATCH p = shortestPath((a:Person {name: $p1})-[:CONNAIT*]-(b:Person {name: $p2}))
                RETURN length(p) AS nb_relations, [n IN nodes(p) | n.name] AS chemin
                """,
                p1=p1, p2=p2,
            ).single()
            if sp and sp.get("nb_relations") is not None:
                return {
                    "p1": p1,
                    "p2": p2,
                    "nb_relations": sp["nb_relations"],
                    "chemin": sp["chemin"],
                }
            else:
                last_res = {"nb_relations": None, "chemin": []}
    # fallback: dernière paire tirée si aucune connectée trouvée
    p1, p2 = last_pair
    return {
        "p1": p1,
        "p2": p2,
        **last_res,
    }


@app.get("/search_people")
def search_people(q: str = Query(..., min_length=1, max_length=64), limit: int = Query(8, ge=1, le=50), fuzzy: int = Query(0, ge=0, le=1)):
    """Recherche des personnes par nom avec correspondance partielle (insensible à la casse).

    - Autorise la saisie avec espaces alors que la BDD a des underscores.
    - Retourne jusqu'à `limit` résultats sous forme de liste de labels exacts (tels que stockés en BDD).
    """
    # Préparer variantes normalisées (sans accents) côté Python
    def _norm(s: str) -> str:
        s = (s or "").strip()
        # ligatures -> ASCII
        s = s.replace("œ", "oe").replace("æ", "ae")
        # remove diacritics
        s = unicodedata.normalize("NFKD", s)
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
        return s.lower()

    q_clean = (q or "").strip()
    if not q_clean:
        return {"results": []}

    # split into tokens (by whitespace) and normalize each token
    raw_tokens = [tok for tok in re.split(r"\s+", q_clean) if tok]
    tokens = [_norm(t) for t in raw_tokens]

    # If fuzzy requested, do a Python-side fuzzy search using difflib over candidate names
    if fuzzy:
        # fetch candidate names (limit to a reasonable amount to avoid huge memory use)
        with driver.session() as session:
            # try to fetch names that contain the first token letter to reduce scan
            try:
                first = raw_tokens[0][:2].lower() if raw_tokens else ''
                q_cypher = "MATCH (p:Person) WHERE toLower(p.name) CONTAINS $first RETURN p.name AS name"
                rows = session.run(q_cypher, first=first).data()
                cand_names = [r['name'] for r in rows]
            except Exception:
                rows = session.run("MATCH (p:Person) RETURN p.name AS name LIMIT 10000").data()
                cand_names = [r['name'] for r in rows]

        # Normalize candidate labels for comparison (underscores -> spaces, remove diacritics)
        norm_map = {}
        for name in cand_names:
            n = _norm(name.replace('_', ' '))
            norm_map[name] = n

        # Build a search key from the raw query (space-normalized)
        search_key = _norm(q_clean.replace('_', ' '))
        # Use difflib to get close matches on the normalized strings
        choices = list(norm_map.values())
        matches = difflib.get_close_matches(search_key, choices, n=limit, cutoff=0.5)
        # Map back to original labels, preserving order and uniqueness
        result = []
        for m in matches:
            for orig, nm in norm_map.items():
                if nm == m and orig not in result:
                    result.append(orig)
                    break
        return {"results": result}

    # Build dynamic WHERE clause: for each token require it to appear (contains)
    # or be a prefix of a word in the space-normalized name. All tokens must match (AND).
    where_parts = []
    params = {"limit": limit}
    for i, tok in enumerate(tokens):
        key = f"t{i}"
        params[key] = tok
        # Use CONTAINS on both underscored and space-normalized forms, or STARTS WITH on split words
        part = f"(norm_u CONTAINS ${key} OR norm_s CONTAINS ${key} OR any(w IN split(norm_s, ' ') WHERE w STARTS WITH ${key}))"
        where_parts.append(part)

    where_clause = " AND ".join(where_parts) if where_parts else "(norm_u CONTAINS $empty OR norm_s CONTAINS $empty)"
    # supply an empty param to avoid cypher errors if no tokens
    params["empty"] = ""

    cypher = f"""
    MATCH (p:Person)
    WITH p,
        toLower(p.name) AS raw_u,
        toLower(replace(p.name, '_', ' ')) AS raw_s
    WITH p,
        replace(replace(raw_u, 'œ','oe'),'æ','ae') AS u1,
        replace(replace(raw_s, 'œ','oe'),'æ','ae') AS s1
    WITH p,
        replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(u1,
         'é','e'),'è','e'),'ê','e'),'ë','e'),'á','a'),'à','a'),'â','a'),'ä','a'),'î','i'),'ï','i'),'ô','o'),'ö','o'),'ù','u'),'û','u'),'ü','u'),'ç','c'),'ñ','n') AS norm_u,
        replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(replace(s1,
         'é','e'),'è','e'),'ê','e'),'ë','e'),'á','a'),'à','a'),'â','a'),'ä','a'),'î','i'),'ï','i'),'ô','o'),'ö','o'),'ù','u'),'û','u'),'ü','u'),'ç','c'),'ñ','n') AS norm_s
    WHERE {where_clause}
    RETURN p.name AS name
    ORDER BY size(p.name) ASC
    LIMIT $limit
    """

    with driver.session() as session:
        res = session.run(cypher, **params)
        names = [r["name"] for r in res]
        return {"results": names}


@app.get("/random_path")
def random_path(max_retries: int = Query(30, ge=1, le=200), min_edges: int = Query(2, ge=1, le=50)):
    """Retourne un chemin aléatoire (chemin le plus court entre deux personnes aléatoires)
    et un index masqué au hasard (pas les extrémités si possible).

    - min_edges: nombre minimal d'arêtes (relations), par défaut 2 => au moins 3 personnes dans le chemin.
    """
    last = None
    with driver.session() as session:
        for _ in range(max_retries):
            rec = session.run(
                """
                MATCH (p:Person)
                WITH p ORDER BY rand() LIMIT 2
                RETURN collect(p.name) AS names
                """
            ).single()
            if not rec:
                continue
            names = rec.get("names") or []
            if len(names) < 2:
                continue
            a, b = names[0], names[1]
            if not a or not b or a == b:
                continue
            sp = session.run(
                """
                MATCH p = shortestPath((a:Person {name: $a})-[:CONNAIT*]-(b:Person {name: $b}))
                RETURN length(p) AS nb_relations, [n IN nodes(p) | n.name] AS chemin
                """,
                a=a, b=b,
            ).single()
            if not sp:
                continue
            nb = sp.get("nb_relations")
            chemin = sp.get("chemin") or []
            if nb is None or not chemin:
                continue
            last = {"nb_relations": nb, "chemin": chemin}
            if nb >= min_edges and len(chemin) >= (min_edges + 1):
                # choisir un index à masquer, idéalement pas les extrémités
                if len(chemin) >= 3:
                    idx = random.randint(1, len(chemin) - 2)
                else:
                    idx = 0  # fallback si seulement 2 noeuds (devrait être exclu par min_edges)
                # Récupérer les catégories du noeud masqué (si présentes)
                cat_rec = session.run(
                    """
                    MATCH (p:Person {name: $ans})
                    RETURN p.categorie_generale AS categories
                    """,
                    ans=chemin[idx],
                ).single()
                categories = []
                if cat_rec is not None:
                    c = cat_rec.get("categories")
                    if isinstance(c, list):
                        categories = c
                return {
                    "chemin": chemin,
                    "masked_index": idx,
                    "answer": chemin[idx],
                    "categories": categories,
                }
    # fallback: retourner le dernier chemin trouvé même s'il est court
    if last:
        chemin = last["chemin"]
        idx = 0 if len(chemin) == 1 else min(1, len(chemin) - 1)
        # récupérer catégories en fallback aussi
        cat_rec = None
        if chemin:
            cat_rec = session.run(
                """
                MATCH (p:Person {name: $ans})
                RETURN p.categorie_generale AS categories
                """,
                ans=chemin[idx],
            ).single()
        categories = []
        if cat_rec is not None:
            c = cat_rec.get("categories")
            if isinstance(c, list):
                categories = c
        return {
            "chemin": chemin,
            "masked_index": idx,
            "answer": chemin[idx] if chemin else None,
            "categories": categories,
        }
    return {"chemin": [], "masked_index": None, "answer": None, "categories": []}

@app.get("/top_degree")
def top_degree(limit: int = Query(10, ge=1, le=100), direction: str = Query("both", regex="^(out|in|both)$")):
    """Retourne les top-K personnes par nombre de relations directes (N+1).

    - direction: 'out' compte (p)-[:CONNAIT]->(q)
                 'in'  compte (q)-[:CONNAIT]->(p)
                 'both' compte les deux directions (UNION distinct)
    """
    if direction == "out":
        cypher = """
        MATCH (p:Person)-[:CONNAIT]->(q:Person)
        RETURN p.name AS name, count(DISTINCT q) AS degree
        ORDER BY degree DESC
        LIMIT $limit
        """
    elif direction == "in":
        cypher = """
        MATCH (p:Person)<-[:CONNAIT]-(q:Person)
        RETURN p.name AS name, count(DISTINCT q) AS degree
        ORDER BY degree DESC
        LIMIT $limit
        """
    elif direction == "both":
        cypher = """
        MATCH (p:Person)-[:CONNAIT]-(other:Person)
        RETURN p.name AS name, COUNT(DISTINCT other) AS degree
        ORDER BY degree DESC
        LIMIT $limit
        """


    with driver.session() as session:
        res = session.run(cypher, limit=limit)
        rows = []
        for r in res:
            rows.append({
                "name": r.get("name"),
                "degree": int(r.get("degree", 0))
            })

    return {"results": rows}

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

@app.get("/shortest_path")
def shortest_path(person1: str = Query(...), person2: str = Query(...)):
    if person1.strip().lower() == person2.strip().lower():
        return JSONResponse(
            status_code=400,
            content={
                "error": "Les deux personnes sont identiques.",
                "message": "Veuillez entrer deux personnes différentes."
            }
        )
    query = """
    MATCH p = shortestPath((a:Person {name: $person1})-[:CONNAIT*]-(b:Person {name: $person2}))
    RETURN length(p) AS nb_relations, [n IN nodes(p) | n.name] AS chemin 
    """
    with driver.session() as session:
        record = session.run(query, person1=person1, person2=person2).single()
        if record:
            return {"nb_relations": record["nb_relations"], "chemin": record["chemin"]}
        else:
            return {"nb_relations": None, "chemin": []}


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
def F(q: str = Query(..., min_length=1, max_length=64), limit: int = Query(8, ge=1, le=50)):
    """Recherche des personnes par nom avec correspondance partielle (insensible à la casse).

    - Autorise la saisie avec espaces alors que la BDD a des underscores.
    - Retourne jusqu'à `limit` résultats sous forme de liste de labels exacts (tels que stockés en BDD).
    """
    # Préparer deux variantes de la requête: avec espaces et avec underscores
    q_clean = (q or "").strip()
    if not q_clean:
        return {"results": []}
    q_space = q_clean
    q_unders = q_clean.replace(" ", "_")

    cypher = """
    MATCH (p:Person)
    WHERE toLower(p.name) CONTAINS toLower($qUnders)
       OR toLower(replace(p.name, '_', ' ')) CONTAINS toLower($qSpace)
    RETURN p.name AS name
    ORDER BY size(p.name) ASC
    LIMIT $limit
    """
    with driver.session() as session:
        res = session.run(cypher, qUnders=q_unders, qSpace=q_space, limit=limit)
        names = [r["name"] for r in res]
        return {"results": names}

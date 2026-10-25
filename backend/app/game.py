"""Endpoints de l'application : chiffres clés, scores, paires populaires, logs de parties."""
import re
import unicodedata

from fastapi import APIRouter, HTTPException, Query, Request
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from .core import pool, state
from .moderation import is_offensive
from .policy import RateLimiter

router = APIRouter()

GAMES = {"guess_count", "guess_who", "relay", "explore", "daily"}
NAME_MAX_LEN = 16


score_limiter = RateLimiter(5, 60)
event_limiter = RateLimiter(240, 60)


@router.get("/stats")
def stats():
    """Chiffres clés pour la page d'accueil (calculés une fois, le graphe ne change qu'à l'import)."""
    if "stats" not in state:
        with pool.connection() as conn:
            counts = conn.execute(
                """SELECT (SELECT count(*) FROM text_link) AS text_links,
                          (SELECT count(*) FROM relation) AS relations,
                          (SELECT count(*) FROM fact) AS facts"""
            ).fetchone()
        state["stats"] = {
            "persons": int(state["graph"].n),
            "links": state["n_edges"],
            **counts,
            "data_date": state["dump_date"],
        }
    return state["stats"]


def normalize_name(name: str) -> str:
    s = unicodedata.normalize("NFKD", name.strip())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z0-9 _-]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return (s or "Anonyme")[:NAME_MAX_LEN]


class ScoreIn(BaseModel):
    game: str
    name: str = Field(..., min_length=1, max_length=40)
    score: int = Field(..., ge=0, le=100_000)
    duration: int = Field(..., ge=1, le=3600)


@router.post("/scores")
def submit_score(payload: ScoreIn, request: Request):
    score_limiter.check(request)
    if payload.game not in GAMES:
        raise HTTPException(400, "Jeu inconnu")
    name = normalize_name(payload.name)
    if is_offensive(name):
        raise HTTPException(422, "Ce pseudo n'est pas accepté, choisissez-en un autre.")
    with pool.connection() as conn:
        row = conn.execute(
            "INSERT INTO app.score (game, name, score, duration) VALUES (%s, %s, %s, %s) RETURNING id",
            (payload.game, name, payload.score, payload.duration),
        ).fetchone()
        rank = conn.execute(
            """SELECT count(*) + 1 AS rank FROM app.score
               WHERE game = %s AND (score > %s OR (score = %s AND duration < %s))""",
            (payload.game, payload.score, payload.score, payload.duration),
        ).fetchone()["rank"]
        total = conn.execute("SELECT count(*) AS n FROM app.score WHERE game = %s", (payload.game,)).fetchone()["n"]
    return {"ok": True, "id": row["id"], "name": name, "rank": rank, "total": total}


@router.get("/leaderboard")
def leaderboard(
    game: str = "guess_count",
    limit: int = Query(10, ge=1, le=100),
    period: str = Query("all", pattern="^(7|30|all)$"),
):
    since = "" if period == "all" else f"AND created_at > now() - interval '{int(period)} days'"
    with pool.connection() as conn:
        rows = conn.execute(
            f"""SELECT name, score, duration, created_at,
                       rank() OVER (ORDER BY score DESC, duration) AS rank
                FROM app.score WHERE game = %s {since}
                ORDER BY score DESC, duration, created_at LIMIT %s""",
            (game, limit),
        ).fetchall()
    return {"game": game, "period": period, "entries": rows}


def record_path_request(a: str, b: str) -> None:
    a, b = sorted((a, b), key=lambda q: int(q[1:]))
    with pool.connection() as conn:
        conn.execute("INSERT INTO app.path_request (a_qid, b_qid) VALUES (%s, %s)", (a, b))


@router.get("/popular_pairs")
def popular_pairs(limit: int = Query(10, ge=1, le=50), period: str = Query("7", pattern="^(7|30|all)$")):
    since = "" if period == "all" else f"WHERE r.created_at > now() - interval '{int(period)} days'"
    with pool.connection() as conn:
        rows = conn.execute(
            f"""SELECT r.a_qid, r.b_qid, count(*) AS count,
                       pa.name AS a_name, pa.image AS a_image, pb.name AS b_name, pb.image AS b_image
                FROM app.path_request r
                JOIN graph.person pa ON pa.qid = r.a_qid
                JOIN graph.person pb ON pb.qid = r.b_qid
                {since}
                GROUP BY r.a_qid, r.b_qid, pa.name, pa.image, pb.name, pb.image
                ORDER BY count DESC LIMIT %s""",
            (limit,),
        ).fetchall()
    return {"period": period, "results": rows}


class EventIn(BaseModel):
    game: str
    session: str | None = Field(None, max_length=64)
    payload: dict


@router.post("/events")
def log_event(event: EventIn, request: Request):
    """Une manche jouée (paire, réponse, vraie distance, temps). Anonyme : pas d'IP stockée."""
    event_limiter.check(request)
    if event.game not in GAMES or len(str(event.payload)) > 4000:
        raise HTTPException(400, "Événement invalide")
    with pool.connection() as conn:
        conn.execute(
            "INSERT INTO app.game_event (game, session, payload, data_version) VALUES (%s, %s, %s, %s)",
            (event.game, event.session, Jsonb(event.payload), state["dump_date"]),
        )
    return {"ok": True}

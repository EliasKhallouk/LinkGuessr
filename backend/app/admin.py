"""Retours des joueurs et tableau de bord privé (jeton dans ADMIN_TOKEN)."""
import hmac

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from .config import ADMIN_TOKEN
from .core import pool
from .game import GAMES
from .policy import RateLimiter

router = APIRouter()
feedback_limiter = RateLimiter(10, 3600)


class FeedbackIn(BaseModel):
    game: str
    rating: int = Field(..., ge=-1, le=1)
    comment: str | None = Field(None, max_length=500)
    src: str | None = Field(None, max_length=40)
    session: str | None = Field(None, max_length=64)


@router.post("/feedback")
def feedback(body: FeedbackIn, request: Request):
    feedback_limiter.check(request)
    if body.game not in GAMES or body.rating == 0:
        raise HTTPException(400, "Retour invalide")
    with pool.connection() as conn:
        conn.execute(
            "INSERT INTO app.feedback (game, rating, comment, src, session) VALUES (%s, %s, %s, %s, %s)",
            (body.game, body.rating, (body.comment or "").strip() or None, body.src, body.session),
        )
    return {"ok": True}


@router.get("/admin/metrics")
def metrics(days: int = Query(7, ge=1, le=90), x_admin_token: str = Header("")):
    """Par jeu et par source : débuts, fins, partages, duels ouverts, et les retours récents."""
    if not ADMIN_TOKEN or not hmac.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(401, "Jeton invalide")
    with pool.connection() as conn:
        funnel = conn.execute(
            """SELECT game, coalesce(payload->>'src', '(direct)') AS src,
                      count(*) FILTER (WHERE payload->>'event' = 'start') AS starts,
                      count(*) FILTER (WHERE payload->>'event' = 'finish') AS finishes,
                      count(*) FILTER (WHERE payload->>'event' = 'share') AS shares,
                      count(*) FILTER (WHERE payload->>'event' = 'duel_open') AS duels,
                      count(DISTINCT session) AS sessions
               FROM app.game_event
               WHERE created_at > now() - make_interval(days => %s) AND payload ? 'event'
               GROUP BY 1, 2 ORDER BY 1, starts DESC""",
            (days,),
        ).fetchall()
        votes = conn.execute(
            """SELECT game, count(*) AS answers, round(100.0 * avg((rating + 1) / 2.0)) AS positive_pct
               FROM app.feedback WHERE created_at > now() - make_interval(days => %s) GROUP BY game""",
            (days,),
        ).fetchall()
        comments = conn.execute(
            """SELECT game, rating, comment, src, created_at FROM app.feedback
               WHERE comment IS NOT NULL AND created_at > now() - make_interval(days => %s)
               ORDER BY created_at DESC LIMIT 50""",
            (days,),
        ).fetchall()
        daily = conn.execute(
            """SELECT day, count(*) FILTER (WHERE cardinality(guesses) > 0) AS players,
                      count(*) FILTER (WHERE solved) AS solved
               FROM app.daily_attempt WHERE day > current_date - %s GROUP BY day ORDER BY day DESC""",
            (days,),
        ).fetchall()
    for row in funnel:
        row["finish_rate"] = round(100 * row["finishes"] / row["starts"]) if row["starts"] else None
        row["share_rate"] = round(100 * row["shares"] / row["finishes"]) if row["finishes"] else None
    return {"days": days, "funnel": funnel, "feedback": votes, "comments": comments, "daily": daily}

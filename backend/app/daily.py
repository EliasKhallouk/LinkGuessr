"""Défi du jour : un chemin A → ? → B dont la personne du milieu est à deviner.

Le même pour tous, il change à minuit (heure de Paris) et il est numéroté (#1 = EPOCH).
Les défis sont pré-calculés (`python -m app.daily generate`) avec un instantané des fiches,
pour rester identiques même si les données sont rechargées entre-temps. La réponse ne
quitte jamais le serveur avant la fin de la partie : chaque proposition est vérifiée ici.

Commandes (sur la VM, avec l'environnement de l'API) :
  python -m app.daily generate [--days 60]        complète les jours manquants
  python -m app.daily set 2026-11-11 --answer Q517 [--from Q… --to Q…]
  python -m app.daily show [--days 14]
"""
import argparse
import datetime as dt
import random
import re
from zoneinfo import ZoneInfo

import numpy as np
from fastapi import APIRouter, HTTPException, Request, Response
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from .core import QID, id_of, path_details, pool, startup, state
from .game import RateLimiter
from .graph import PathResult
from .moderation import is_offensive

router = APIRouter()

PARIS = ZoneInfo("Europe/Paris")
EPOCH = dt.date(2026, 10, 26)  # défi n°1
MAX_TRIES = 4                  # erreurs avant de révéler la réponse
ANSWER_TOP = 0.005             # personne cachée parmi les 0,5 % les plus populaires (~3 800)
ENDPOINT_TOP = 0.02            # extrémités du chemin parmi les 2 % (~15 000)
guess_limiter = RateLimiter(60, 60)
pseudo_limiter = RateLimiter(5, 60)


def today() -> dt.date:
    return dt.datetime.now(PARIS).date()


def number_of(day: dt.date) -> int:
    return (day - EPOCH).days + 1


def seconds_until_midnight() -> int:
    now = dt.datetime.now(PARIS)
    midnight = dt.datetime.combine(now.date() + dt.timedelta(days=1), dt.time(), PARIS)
    return max(1, int((midnight - now).total_seconds()))


# --- Génération --------------------------------------------------------------------------

def _history_item(answer: dict) -> dict:
    return {"domain": answer.get("primary_domain"), "century": (answer.get("birth_year") or 0) // 100,
            "country": answer.get("country"), "gender": answer.get("gender")}


def _candidates(conn) -> list[dict]:
    pop = state["graph"].popularity
    ids = np.flatnonzero(pop >= np.quantile(pop, 1 - ANSWER_TOP)).tolist()
    return conn.execute(
        """SELECT id, qid, name, primary_domain, birth_year, gender,
                  coalesce(birth_country, citizenships[1]) AS country
           FROM person WHERE id = ANY(%s) AND primary_domain IS NOT NULL AND birth_year IS NOT NULL""",
        (ids,),
    ).fetchall()


def best_pair(x: int) -> tuple[int, int, int] | None:
    """Deux voisins connus de x qui ne se connaissent pas : x est alors sur un plus court chemin a → x → b.
    On préfère peu d'intermédiaires possibles (réponse déductible), des extrémités connues et de domaines différents."""
    graph = state["graph"]
    csr, pop, domain = graph.csr["all"], graph.popularity, state["domain"]
    threshold = state.setdefault("daily_endpoint_threshold", float(np.quantile(pop, 1 - ENDPOINT_TOP)))
    neighbors = csr.neighbors_of(x)
    neighbors = neighbors[pop[neighbors] >= threshold]
    neighbors = neighbors[np.argsort(-pop[neighbors])][:25]
    sets = {int(v): set(csr.neighbors_of(int(v)).tolist()) for v in neighbors}
    best = None
    for i, a in enumerate(neighbors.tolist()):
        for b in neighbors[i + 1:].tolist():
            if b in sets[a]:
                continue
            common = len(sets[a] & sets[b])  # personnes possibles au milieu, x compris
            score = float(pop[a] + pop[b]) + 0.3 * (domain[a] != domain[b]) - 0.05 * (common - 1)
            if best is None or score > best[0]:
                best = (score, a, b, common)
    return best[1:] if best else None


def _pick(candidates: list[dict], history: list[dict], rng: random.Random):
    """Personne du jour : variée par rapport aux jours précédents (domaine, siècle, pays, genre)."""
    women = sum(h["gender"] == "femme" for h in history[-10:])

    def score(c: dict) -> float:
        s = rng.random()
        if any(h["domain"] == c["primary_domain"] for h in history[-3:]):
            s -= 2
        if any(h["century"] == c["birth_year"] // 100 for h in history[-2:]):
            s -= 1
        if c["country"] and any(h["country"] == c["country"] for h in history[-2:]):
            s -= 1
        if c["gender"] == "femme" and women < 3:
            s += 1
        return s

    for c in sorted(candidates, key=score, reverse=True)[:200]:
        if pair := best_pair(c["id"]):
            return c, pair
    raise RuntimeError("aucun candidat valable")


def _store(conn, day: dt.date, a: int, x: int, b: int, common: int, country: str | None, forced: bool) -> dict:
    details = path_details(PathResult(2, common, [[a, x, b]]))
    persons = details["persons"]
    path = details["paths"][0]
    answer = {**persons[path[1]], "country": country}
    hints = {
        "domain": answer["primary_domain"],
        "birth_year": answer["birth_year"],
        "death_year": answer["death_year"],
        "initials": "".join(w[0] for w in re.split(r"[\s-]+", answer["name"]) if w),
        "name_length": len(answer["name"]),
    }
    conn.execute(
        """INSERT INTO app.daily_challenge (day, number, path, masked_index, answer, persons, hops, hints, forced)
           VALUES (%s, %s, %s, 1, %s, %s, %s, %s, %s)
           ON CONFLICT (day) DO UPDATE SET path = EXCLUDED.path, answer = EXCLUDED.answer, persons = EXCLUDED.persons,
             hops = EXCLUDED.hops, hints = EXCLUDED.hints, forced = EXCLUDED.forced, created_at = now()""",
        (day, number_of(day), path, Jsonb(answer), Jsonb(persons), Jsonb(details["hops"]), Jsonb(hints), forced),
    )
    return answer


def generate(days: int = 60, start: dt.date | None = None) -> int:
    """Complète les `days` prochains jours sans toucher aux jours déjà définis (ni aux forçages)."""
    start = start or today()
    created = 0
    with pool.connection() as conn:
        existing = {r["day"]: r["answer"] for r in conn.execute("SELECT day, answer FROM app.daily_challenge").fetchall()}
        used = {a["qid"] for a in existing.values()}
        history = [_history_item(a) for d, a in sorted(existing.items()) if d < start]
        candidates = [c for c in _candidates(conn) if c["qid"] not in used]
        for offset in range(days):
            day = start + dt.timedelta(days=offset)
            if day in existing:
                history.append(_history_item(existing[day]))
                continue
            c, (a, b, common) = _pick(candidates, history, random.Random(day.isoformat()))
            answer = _store(conn, day, a, c["id"], b, common, c["country"], forced=False)
            candidates.remove(c)
            history.append(_history_item(answer))
            created += 1
    return created


def force(day: dt.date, answer_qid: str, from_qid: str | None = None, to_qid: str | None = None) -> dict:
    x = id_of(answer_qid)
    if from_qid and to_qid:
        a, b = id_of(from_qid), id_of(to_qid)
        res = state["graph"].shortest_paths(a, b, limit=1)
        common = res.n_paths
    else:
        pair = best_pair(x)
        if not pair:
            raise SystemExit(f"{answer_qid} : aucune paire de voisins connus qui ne se connaissent pas, préciser --from/--to")
        a, b, common = pair
    with pool.connection() as conn:
        country = conn.execute("SELECT coalesce(birth_country, citizenships[1]) AS c FROM person WHERE id = %s",
                               (x,)).fetchone()["c"]
        return _store(conn, day, a, x, b, common, country, forced=True)


# --- API ---------------------------------------------------------------------------------

def _today_row() -> dict:
    day = today()
    with pool.connection() as conn:
        row = conn.execute("SELECT * FROM app.daily_challenge WHERE day = %s", (day,)).fetchone()
    if row is None:  # filet de sécurité si la génération planifiée n'a pas tourné
        generate(days=1, start=day)
        with pool.connection() as conn:
            row = conn.execute("SELECT * FROM app.daily_challenge WHERE day = %s", (day,)).fetchone()
    return row


def _public(row: dict, reveal: bool) -> dict:
    masked = row["path"][row["masked_index"]]
    hidden = lambda key: masked in key.split("-")  # noqa: E731
    return {
        "number": row["number"],
        "day": row["day"].isoformat(),
        "path": row["path"],
        "masked_index": row["masked_index"],
        "persons": row["persons"] if reveal else {q: p for q, p in row["persons"].items() if q != masked},
        "hops": row["hops"] if reveal else {k: v for k, v in row["hops"].items() if not hidden(k)},
        "max_tries": MAX_TRIES,
        **({"answer": row["answer"]} if reveal else {}),
    }


@router.get("/daily")
def daily(response: Response):
    """Le défi du jour, sans la réponse. Identique pour tous : mis en cache jusqu'à minuit (au plus 1 h)."""
    response.headers["Cache-Control"] = f"public, max-age=60, s-maxage={min(seconds_until_midnight(), 3600)}"
    return _public(_today_row(), reveal=False)


@router.get("/daily/archive/{number}")
def daily_archive(number: int, response: Response):
    """Un défi passé, réponse comprise (les liens partagés restent consultables après minuit).
    Le défi du jour et les suivants ne sont jamais révélés ici."""
    with pool.connection() as conn:
        row = conn.execute("SELECT * FROM app.daily_challenge WHERE number = %s", (number,)).fetchone()
    if row is None:
        raise HTTPException(404, "Défi inconnu")
    if row["day"] >= today():
        response.headers["Cache-Control"] = "public, max-age=60, s-maxage=300"
        return {**_public(row, reveal=False), "current": row["day"] == today()}
    response.headers["Cache-Control"] = "public, max-age=3600, s-maxage=86400"
    return {**_public(row, reveal=True), "current": False}


class GuessIn(BaseModel):
    device: str = Field(..., min_length=8, max_length=64)
    qid: str | None = None  # absent : renvoie seulement l'état de la partie


@router.post("/daily/guess")
def daily_guess(body: GuessIn, request: Request):
    """Une proposition (ou l'état courant). Indices débloqués à chaque erreur, réponse révélée à la fin."""
    guess_limiter.check(request)
    if body.qid and not QID.match(body.qid):
        raise HTTPException(400, "QID invalide")
    row = _today_row()
    masked = row["path"][row["masked_index"]]
    with pool.connection() as conn:
        attempt = conn.execute(
            """INSERT INTO app.daily_attempt (day, device) VALUES (%s, %s)
               ON CONFLICT (day, device) DO UPDATE SET device = EXCLUDED.device RETURNING *""",
            (row["day"], body.device),
        ).fetchone()
        if body.qid and not attempt["finished"] and body.qid not in attempt["guesses"]:
            guesses = attempt["guesses"] + [body.qid]
            solved = body.qid == masked
            finished = solved or sum(g != masked for g in guesses) >= MAX_TRIES
            attempt = conn.execute(
                """UPDATE app.daily_attempt SET guesses = %s, solved = %s, finished = %s,
                          finished_at = CASE WHEN %s THEN now() ELSE NULL END
                   WHERE day = %s AND device = %s RETURNING *""",
                (guesses, solved, finished, finished, row["day"], body.device),
            ).fetchone()
        wrong = [g for g in attempt["guesses"] if g != masked]
        names = {r["qid"]: r["name"] for r in conn.execute(
            "SELECT qid, name FROM person WHERE qid = ANY(%s)", (wrong,)).fetchall()}
        stats = conn.execute(
            """SELECT count(*) FILTER (WHERE finished) AS players, count(*) FILTER (WHERE solved) AS solved
               FROM app.daily_attempt WHERE day = %s""",
            (row["day"],),
        ).fetchone() if attempt["finished"] else None

    hints = row["hints"]
    unlocked = [
        {"kind": "domain", "value": hints["domain"]},
        {"kind": "life", "birth_year": hints["birth_year"], "death_year": hints["death_year"]},
        {"kind": "initials", "value": hints["initials"], "length": hints["name_length"]},
    ][:len(wrong)]
    return {
        **_public(row, reveal=attempt["finished"]),
        "tries": len(attempt["guesses"]),
        "wrong": [{"qid": q, "name": names.get(q, q)} for q in wrong],
        "solved": attempt["solved"],
        "finished": attempt["finished"],
        "hints": unlocked,
        "stats": stats,
    }


class PseudoIn(BaseModel):
    device: str = Field(..., min_length=8, max_length=64)
    pseudo: str = Field(..., min_length=1, max_length=40)


@router.post("/daily/pseudo")
def daily_pseudo(body: PseudoIn, request: Request):
    """Pseudo facultatif pour le classement du jour, réservé à ceux qui ont trouvé."""
    from .game import normalize_name  # même normalisation que le classement des scores

    pseudo_limiter.check(request)
    pseudo = normalize_name(body.pseudo)
    if is_offensive(pseudo):
        raise HTTPException(422, "Ce pseudo n'est pas accepté, choisissez-en un autre.")
    day = today()
    with pool.connection() as conn:
        attempt = conn.execute("SELECT solved FROM app.daily_attempt WHERE day = %s AND device = %s",
                               (day, body.device)).fetchone()
        if not attempt or not attempt["solved"]:
            raise HTTPException(403, "Le classement est réservé à ceux qui ont trouvé la réponse.")
        taken = conn.execute(
            "SELECT 1 FROM app.daily_attempt WHERE day = %s AND lower(pseudo) = lower(%s) AND device <> %s",
            (day, pseudo, body.device)).fetchone()
        if taken:
            raise HTTPException(409, "Ce pseudo est déjà pris aujourd'hui.")
        conn.execute("UPDATE app.daily_attempt SET pseudo = %s WHERE day = %s AND device = %s",
                     (pseudo, day, body.device))
    return {"ok": True, "pseudo": pseudo}


@router.get("/daily/leaderboard")
def daily_leaderboard(response: Response, limit: int = 20):
    """Classement du jour : moins d'essais d'abord, puis le plus rapide."""
    response.headers["Cache-Control"] = "public, max-age=30, s-maxage=30"
    with pool.connection() as conn:
        rows = conn.execute(
            """SELECT pseudo, cardinality(guesses) AS tries,
                      extract(epoch FROM finished_at - started_at)::int AS seconds
               FROM app.daily_attempt
               WHERE day = %s AND solved AND pseudo IS NOT NULL
               ORDER BY tries, seconds LIMIT %s""",
            (today(), min(max(limit, 1), 100)),
        ).fetchall()
    return {"day": today().isoformat(), "entries": rows}


# --- Ligne de commande ---------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.daily", description="Défis du jour")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("generate", help="complète les jours manquants")
    p.add_argument("--days", type=int, default=60)
    p = sub.add_parser("set", help="force le défi d'une date")
    p.add_argument("day", type=dt.date.fromisoformat)
    p.add_argument("--answer", required=True)
    p.add_argument("--from", dest="from_qid")
    p.add_argument("--to", dest="to_qid")
    p = sub.add_parser("show", help="affiche les prochains défis")
    p.add_argument("--days", type=int, default=14)
    args = parser.parse_args()

    startup()
    if args.cmd == "generate":
        print(f"{generate(args.days)} défi(s) créé(s)")
    elif args.cmd == "set":
        answer = force(args.day, args.answer, args.from_qid, args.to_qid)
        print(f"{args.day} (#{number_of(args.day)}) : {answer['name']}")
    if args.cmd in ("generate", "set", "show"):
        with pool.connection() as conn:
            for r in conn.execute(
                """SELECT day, number, answer, persons, path, forced FROM app.daily_challenge
                   WHERE day >= %s ORDER BY day LIMIT %s""", (today(), getattr(args, "days", 14))).fetchall():
                a, p = r["answer"], r["persons"]
                print(f"#{r['number']:>3} {r['day']} {'(forcé) ' if r['forced'] else ''}"
                      f"{p[r['path'][0]]['name']} → [{a['name']} · {a['primary_domain']} · {a['birth_year']}"
                      f" · {a['gender']}] → {p[r['path'][2]]['name']}")
    pool.close()


if __name__ == "__main__":
    main()

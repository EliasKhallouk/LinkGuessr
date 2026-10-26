"""Défi du jour : un chemin A → ? → B dont la personne du milieu est à deviner.

Recette : A est une personnalité que les jeunes connaissent aujourd'hui (rap, web, pop, foot,
à tour de rôle), B une personnalité célèbre qui n'a rien à voir (autre époque ou autre univers :
histoire, politique, sciences…), et la personne cachée est l'intermédiaire, assez connue pour
être devinée.

Le même pour tous, il change à minuit (heure de Paris) et il est numéroté (#1 = EPOCH).
Les défis sont pré-calculés (`python -m app.daily generate`) avec un instantané des fiches,
pour rester identiques même si les données sont rechargées entre-temps. La réponse ne
quitte jamais le serveur avant la fin de la partie : chaque proposition est vérifiée ici.

Commandes (sur la VM, avec l'environnement de l'API) :
  python -m app.daily generate [--days 60]        complète les jours manquants
  python -m app.daily generate --replace-from 2026-10-27   recalcule les jours non forcés à partir d'une date
  python -m app.daily preview [--days 14]         aperçu des défis que la recette choisirait (rien n'est écrit)
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
from .policy import RateLimiter
from .graph import PathResult
from .moderation import is_offensive

router = APIRouter()

PARIS = ZoneInfo("Europe/Paris")
EPOCH = dt.date(2026, 10, 26)  # défi n°1
MAX_TRIES = 4                  # erreurs avant de révéler la réponse
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


# --- Génération ---------------------------------------------------------------------------

# Personnalités que les jeunes connaissent : métiers Wikidata (vérifiés sur les données).
YOUTH_KINDS = ["rap", "web", "pop", "foot"]  # une catégorie par jour, à tour de rôle
RAP = {"Q2252262"}                                                       # rappeur
WEB = {"Q17125263", "Q57414145", "Q4110598", "Q2906862", "Q50279140",  # youtubeur, streamer, vlogueur,
       "Q48938223", "Q94791573"}                                         # influenceur, streameur Twitch, tiktokeur
POP, FOOT = "Q177220", "Q937857"                                        # chanteur, footballeur
YOUTH_MIN_VIEWS = 50_000   # pages vues sur 12 mois
CONTRAST_TOP = 3_000       # la personnalité « sans rapport » est parmi les 3 000 plus populaires
MIDDLE_TOP = 0.02          # la personne cachée est dans le top 2 % : devinable
NO_REPEAT_DAYS = 30        # ni la star ni la personnalité « sans rapport » ne reviennent avant 30 jours
FAMILIES = {
    "politique": "pouvoir", "militaire": "pouvoir", "noblesse": "pouvoir", "droit": "pouvoir", "religion": "pouvoir",
    "sciences": "savoirs", "sciences humaines": "savoirs", "éducation": "savoirs", "littérature": "savoirs",
}


def youth_kind(row: dict) -> str | None:
    occupations, born = set(row["occupations"] or []), row["birth_year"] or 0
    if occupations & RAP and born >= 1975:
        return "rap"
    if occupations & WEB and born >= 1980:
        return "web"
    if POP in occupations and born >= 1990:
        return "pop"
    if FOOT in occupations and born >= 1996:
        return "foot"
    return None


def _youth(conn) -> dict[int, dict]:
    rows = conn.execute(
        """SELECT id, qid, name, birth_year, occupations, pageviews_12m FROM person
           WHERE death_year IS NULL AND birth_year >= 1975 AND pageviews_12m >= %s AND occupations && %s""",
        (YOUTH_MIN_VIEWS, sorted(RAP | WEB | {POP, FOOT})),
    ).fetchall()
    youth = {r["id"]: {**r, "kind": kind} for r in rows if (kind := youth_kind(r))}
    for rank, i in enumerate(sorted(youth, key=lambda i: -youth[i]["pageviews_12m"])):
        youth[i]["fame"] = 1 - rank / len(youth)  # notoriété actuelle, parmi les jeunes
    return youth


def _contrasts(conn) -> dict[int, dict]:
    ids = np.argsort(-state["graph"].popularity)[:CONTRAST_TOP].tolist()
    rows = conn.execute("SELECT id, qid, name, birth_year, primary_domain FROM person WHERE id = ANY(%s)", (ids,)).fetchall()
    return {r["id"]: r for r in rows
            if (r["birth_year"] is not None and r["birth_year"] <= 1900) or FAMILIES.get(r["primary_domain"])}


def _triplets(youth: dict, contrasts: dict) -> list[dict]:
    """Tous les chemins jeune → intermédiaire connu → sans rapport, à distance exactement 2, avec leur score."""
    graph = state["graph"]
    csr, strong, pop = graph.csr["all"], graph.csr["strong"], graph.popularity
    middle_min = float(np.quantile(pop, 1 - MIDDLE_TOP))
    neighbor_sets: dict[int, set] = {}

    def neighbors(v: int, g=csr) -> set:
        key = v if g is csr else -v - 1
        if key not in neighbor_sets:
            neighbor_sets[key] = set(g.neighbors_of(v).tolist())
        return neighbor_sets[key]

    out = []
    for y, info in youth.items():
        ny, strong_y = neighbors(y), neighbors(y, strong)
        for m in ny:
            if pop[m] < middle_min or m in contrasts:
                continue
            strong_m = neighbors(m, strong)
            for c in csr.neighbors_of(m).tolist():
                if c not in contrasts or c == y or c in ny:
                    continue
                cinfo = contrasts[c]
                alternatives = len(ny & neighbors(c))  # personnes possibles au milieu (la bonne comprise)
                era = min(abs((info["birth_year"] or 2000) - (cinfo["birth_year"] or 2000)) / 400, 1.0)
                strength = ((m in strong_y) + (c in strong_m)) / 2
                score = (1.0 * info["fame"] + 0.8 * era + 0.5 * float(pop[c]) + 0.7 * float(pop[m])
                         + 0.4 * strength - 0.08 * min(alternatives - 1, 10))
                out.append({"youth": y, "middle": m, "contrast": c, "kind": info["kind"],
                            "alternatives": alternatives, "score": score})
    return out


def plan(days: int, start: dt.date, existing: dict[dt.date, dict]) -> list[tuple[dt.date, dict]]:
    """Défis des `days` jours à partir de `start` (sans écrire) : catégorie du jour, meilleur score,
    pas de répétition récente de la star ni de la personnalité « sans rapport », réponse jamais réutilisée."""
    with pool.connection() as conn:
        youth, contrasts = _youth(conn), _contrasts(conn)
    triplets = _triplets(youth, contrasts)
    qid_of = lambda i: youth[i]["qid"] if i in youth else contrasts[i]["qid"] if i in contrasts else None  # noqa: E731
    used_answers = {row["answer"]["qid"] for row in existing.values()}
    recent = [(d, row["path"][0], row["path"][-1]) for d, row in existing.items()]
    chosen = []
    for offset in range(days):
        day = start + dt.timedelta(days=offset)
        if day in existing:
            continue
        kind = YOUTH_KINDS[day.toordinal() % len(YOUTH_KINDS)]
        window = {q for d, *qs in recent if 0 < (day - d).days <= NO_REPEAT_DAYS for q in qs}
        rng = random.Random(day.isoformat())
        best = None
        for t in triplets:
            if t["kind"] != kind or qid_of(t["youth"]) in window or qid_of(t["contrast"]) in window:
                continue
            middle_qid = state["qid_num"][t["middle"]]
            if f"Q{middle_qid}" in used_answers:
                continue
            value = t["score"] + rng.uniform(0, 0.15)  # un peu de hasard pour varier
            if best is None or value > best[0]:
                best = (value, t)
        if best is None:
            raise RuntimeError(f"{day} : aucun défi possible pour la catégorie {kind}")
        t = best[1]
        chosen.append((day, t))
        used_answers.add(f"Q{state['qid_num'][t['middle']]}")
        recent.append((day, qid_of(t["youth"]), qid_of(t["contrast"])))
    return chosen


def best_pair(x: int) -> tuple[int, int, int] | None:
    """Pour un forçage sans --from/--to : deux voisins connus de x qui ne se connaissent pas (a → x → b)."""
    graph = state["graph"]
    csr, pop, domain = graph.csr["all"], graph.popularity, state["domain"]
    threshold = float(np.quantile(pop, 0.98))
    neighbors = csr.neighbors_of(x)
    neighbors = neighbors[pop[neighbors] >= threshold]
    neighbors = neighbors[np.argsort(-pop[neighbors])][:25]
    sets = {int(v): set(csr.neighbors_of(int(v)).tolist()) for v in neighbors}
    best = None
    for i, a in enumerate(neighbors.tolist()):
        for b in neighbors[i + 1:].tolist():
            if b in sets[a]:
                continue
            common = len(sets[a] & sets[b])
            score = float(pop[a] + pop[b]) + 0.3 * (domain[a] != domain[b]) - 0.05 * (common - 1)
            if best is None or score > best[0]:
                best = (score, a, b, common)
    return best[1:] if best else None


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


def _existing(conn, keep_before: dt.date | None = None) -> dict[dt.date, dict]:
    rows = conn.execute("SELECT day, path, answer, forced FROM app.daily_challenge").fetchall()
    return {r["day"]: r for r in rows if keep_before is None or r["day"] < keep_before or r["forced"]}


def generate(days: int = 60, start: dt.date | None = None, replace_from: dt.date | None = None) -> int:
    """Complète les `days` prochains jours. Avec `replace_from`, recalcule d'abord les jours non forcés
    à partir de cette date (les jours passés, celui en cours et les forçages ne bougent jamais)."""
    start = start or today()
    if replace_from is not None:
        if replace_from <= today():
            raise SystemExit("--replace-from doit être postérieur à aujourd'hui (le défi du jour est déjà en jeu)")
        with pool.connection() as conn:
            conn.execute("DELETE FROM app.daily_challenge WHERE day >= %s AND NOT forced", (replace_from,))
    with pool.connection() as conn:
        existing = _existing(conn)
        chosen = plan(days, start, existing)
        country = {r["id"]: r["c"] for r in conn.execute(
            "SELECT id, coalesce(birth_country, citizenships[1]) AS c FROM person WHERE id = ANY(%s)",
            ([t["middle"] for _, t in chosen],)).fetchall()}
        for day, t in chosen:
            _store(conn, day, t["youth"], t["middle"], t["contrast"], t["alternatives"], country.get(t["middle"]),
                   forced=False)
    return len(chosen)


def preview(days: int = 14, start: dt.date | None = None) -> None:
    """Ce que la recette choisirait pour les jours non forcés à partir de demain (rien n'est écrit)."""
    start = start or today() + dt.timedelta(days=1)
    with pool.connection() as conn:
        existing = _existing(conn, keep_before=start)
        chosen = plan(days, start, existing)
        names = {r["id"]: r for r in conn.execute(
            "SELECT id, name, description, birth_year, primary_domain FROM person WHERE id = ANY(%s)",
            ([i for _, t in chosen for i in (t["youth"], t["middle"], t["contrast"])],)).fetchall()}
    for day, t in chosen:
        y, m, c = names[t["youth"]], names[t["middle"]], names[t["contrast"]]
        print(f"#{number_of(day):>3} {day} [{t['kind']:<4}] {y['name']} → [{m['name']} · {m['description'] or ''}]"
              f" → {c['name']} ({c['birth_year']}, {c['primary_domain']})  | {t['alternatives']} possible(s)")


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
    p.add_argument("--replace-from", type=dt.date.fromisoformat, help="recalcule les jours non forcés dès cette date")
    p = sub.add_parser("preview", help="aperçu de la recette, sans rien écrire")
    p.add_argument("--days", type=int, default=14)
    p = sub.add_parser("set", help="force le défi d'une date")
    p.add_argument("day", type=dt.date.fromisoformat)
    p.add_argument("--answer", required=True)
    p.add_argument("--from", dest="from_qid")
    p.add_argument("--to", dest="to_qid")
    p = sub.add_parser("show", help="affiche les prochains défis")
    p.add_argument("--days", type=int, default=14)
    args = parser.parse_args()

    startup()
    if args.cmd == "preview":
        preview(args.days)
        pool.close()
        return
    if args.cmd == "generate":
        print(f"{generate(args.days, replace_from=args.replace_from)} défi(s) créé(s)")
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

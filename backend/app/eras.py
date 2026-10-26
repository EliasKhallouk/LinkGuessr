"""Époques de « Qui est caché ? » : aujourd'hui (les gens que connaissent les jeunes), culture générale, histoire.

Pour chaque époque : les personnes concernées, de la plus connue à la moins connue (`order`), et le rang de chaque
personne dans ce classement (`rank`, 1 = la plus connue ; hors de l'époque : au-delà du dernier rang).
"""
import numpy as np

from .core import pool, state
from .daily import EXCLUDED_OCCUPATIONS, FOOT, POP, RAP, WEB

ERAS = ["aujourdhui", "tous", "histoire"]
BORN_FROM = 1970   # aujourd'hui : vivants nés à partir de 1970
DIED_BEFORE = 1950  # histoire : morts avant 1950
# Aujourd'hui = ce que connaissent les jeunes. Les pages vues de Wikipédia en français reflètent surtout un public
# adulte (acteurs de téléfilms, animateurs, élus) : on ne garde que les métiers des jeunes (rap, YouTube et
# streaming, chanteurs, foot), quelle que soit leur notoriété ailleurs, et sinon les stars internationales
# (au moins INTERNATIONAL Wikipédias : Zendaya, Chalamet, Musk ; pas Benjamin Lavernhe ni Alice Taglioni).
YOUTH_JOBS = sorted(RAP | WEB | {POP, FOOT})
INTERNATIONAL = 40
# Rappeurs, youtubeurs, streamers : bien plus connus des jeunes que ne le disent leurs pages vues sur Wikipédia.
YOUTH_BOOST = 3


def load_eras() -> None:
    n = state["graph"].n
    with pool.connection() as conn:
        rows = conn.execute(
            """SELECT id, birth_year, death_year, gender, coalesce(pageviews_12m, 0) AS views,
                      coalesce(occupations && %s, false) AS youth,
                      coalesce(occupations && %s, false) OR coalesce(sitelinks, 0) >= %s AS known_young,
                      coalesce(occupations && %s, false) AS excluded FROM person""",
            (sorted(RAP | WEB), YOUTH_JOBS, INTERNATIONAL, EXCLUDED_OCCUPATIONS),
        ).fetchall()
    ids = np.array([r["id"] for r in rows])
    born = np.full(n, -10_000, dtype=np.int32)
    died = np.full(n, 10_000, dtype=np.int32)   # pas de date de décès : vivant (ou inconnu)
    views = np.zeros(n, dtype=np.float64)
    youth = np.zeros(n, dtype=bool)
    known_young = np.zeros(n, dtype=bool)
    excluded = np.zeros(n, dtype=bool)
    born[ids] = [r["birth_year"] if r["birth_year"] is not None else -10_000 for r in rows]
    died[ids] = [r["death_year"] if r["death_year"] is not None else 10_000 for r in rows]
    views[ids] = [r["views"] for r in rows]
    youth[ids] = [r["youth"] for r in rows]
    known_young[ids] = [r["known_young"] for r in rows]
    excluded[ids] = [r["excluded"] for r in rows]
    # Pour les leurres du choix multiple (personnes qui ressemblent à la cachée) : naissance et genre.
    gender = np.zeros(n, dtype=np.int8)
    gender[ids] = [{"homme": 1, "femme": 2}.get(r["gender"], 0) for r in rows]
    state["born"], state["gender"] = born, gender

    popularity = state["graph"].popularity
    # Aujourd'hui : notoriété actuelle (pages vues des 12 derniers mois), pas le score global qui favorise l'histoire.
    today = (died == 10_000) & (born >= BORN_FROM) & known_young & ~excluded
    specs = {
        "aujourdhui": (today, views * np.where(youth, YOUTH_BOOST, 1)),
        "tous": (np.ones(n, dtype=bool), popularity),
        "histoire": (died < DIED_BEFORE, popularity),
    }
    state["eras"] = {}
    for era, (mask, score) in specs.items():
        members = np.flatnonzero(mask)
        order = members[np.argsort(-score[members], kind="stable")]
        rank = np.full(n, n + 1, dtype=np.int64)
        rank[order] = np.arange(1, len(order) + 1)
        state["eras"][era] = {"order": order, "rank": rank}

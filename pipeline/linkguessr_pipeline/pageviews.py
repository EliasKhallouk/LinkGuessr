"""Pages vues de chaque biographie sur frwiki, mois par mois, sur les 12 derniers mois.

Source : API Pageviews de Wikimedia (lecteurs humains uniquement, agent=user).
Wikimedia tolère 100 requêtes/s sur cette API ; on reste en dessous avec 16 requêtes
en parallèle. Les fichiers mensuels équivalents pèsent 6 Go par mois (tous wikis).

Sortie : pageviews.parquet  qid, pageviews_12m, pageviews_monthly (12 valeurs, du plus ancien au plus récent)
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from urllib.parse import quote

import polars as pl
from tqdm import tqdm

from .config import DUMP_DATE, work_path
from .http import make_session

API = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/fr.wikipedia.org/all-access/user/"
       "{title}/monthly/{start}/{end}")
SHARD = 10_000
WORKERS = 16


def _period() -> tuple[list[str], str, str]:
    """Les 12 mois complets qui précèdent la date du dump."""
    d = date(int(DUMP_DATE[:4]), int(DUMP_DATE[4:6]), 1)
    months = []
    for _ in range(12):
        d = date(d.year - (d.month == 1), 12 if d.month == 1 else d.month - 1, 1)
        months.append(f"{d.year:04d}{d.month:02d}")
    months.reverse()
    return months, f"{months[0]}0100", f"{months[-1]}2800"


def fetch_pageviews() -> None:
    humans = pl.read_parquet(work_path("humans.parquet")).sort("qid")
    months, start, end = _period()
    out_dir = work_path("pageviews")
    out_dir.mkdir(exist_ok=True)
    session = make_session(pool_size=WORKERS)

    def views(title: str) -> list[int]:
        r = session.get(API.format(title=quote(title, safe=""), start=start, end=end), timeout=60)
        if r.status_code == 404:  # aucune vue enregistrée sur la période
            return [0] * len(months)
        r.raise_for_status()
        by_month = {item["timestamp"][:6]: item["views"] for item in r.json()["items"]}
        return [by_month.get(m, 0) for m in months]

    shards = [humans.slice(i, SHARD) for i in range(0, humans.height, SHARD)]
    print(f"{humans.height:,} pages, période {months[0]} → {months[-1]}, {len(shards)} fragments")
    with ThreadPoolExecutor(WORKERS) as pool:
        for i, shard in enumerate(tqdm(shards, desc="pageviews", unit="fragment")):
            path = out_dir / f"{i:05d}.parquet"
            if path.exists():
                continue
            monthly = list(pool.map(views, shard["title"].to_list()))
            pl.DataFrame({
                "qid": shard["qid"],
                "pageviews_12m": [sum(m) for m in monthly],
                "pageviews_monthly": monthly,
            }, schema={"qid": pl.Utf8, "pageviews_12m": pl.Int64, "pageviews_monthly": pl.List(pl.Int32)}
            ).write_parquet(path)

    result = pl.concat([pl.read_parquet(p) for p in sorted(out_dir.glob("*.parquet"))])
    result.write_parquet(work_path("pageviews.parquet"))
    print(f"{result.height:,} pages, {result['pageviews_12m'].sum():,} vues au total")

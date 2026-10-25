"""Pages vues frwiki sur les 12 mois qui précèdent le dump.

Source : fichiers mensuels officiels « pageview_complete » (lecteurs humains, agent=user),
environ 6 Go par mois pour tous les wikis. L'API Pageviews limite trop fort le débit
(erreurs 429) pour 760 000 requêtes.

Deux temps :
  1. `lg pageviews-dump` (sur la VM, connexion rapide) : lit chaque fichier en flux,
     ne garde que les lignes « fr.wikipedia », écrit pageviews_dumps/AAAAMM.tsv.gz (titre, vues).
     Les lignes sont triées par wiki : on saute tout ce qui précède frwiki et on s'arrête après.
  2. `lg pageviews` (sur le PC) : joint ces fichiers aux biographies, en ajoutant les vues des
     redirections à leur cible. Sortie : pageviews.parquet
       qid, pageviews_12m, pageviews_monthly (12 valeurs, du plus ancien au plus récent)
"""
import bz2
import gzip
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

import polars as pl
import requests

from .config import DUMP_DATE, work_path
from .download import MIRROR
from .http import make_session

PREFIX = "fr.wikipedia "
MAX_RESUMES = 50


def months_before_dump() -> list[str]:
    """Les 12 mois complets qui précèdent la date du dump, du plus ancien au plus récent."""
    d = date(int(DUMP_DATE[:4]), int(DUMP_DATE[4:6]), 1)
    months = []
    for _ in range(12):
        d = date(d.year - (d.month == 1), 12 if d.month == 1 else d.month - 1, 1)
        months.append(f"{d.year:04d}{d.month:02d}")
    return months[::-1]


def _month_url(month: str) -> str:
    base = MIRROR.removesuffix("/dumps")  # les pages vues sont sous /other, pas /dumps
    return f"{base}/other/pageview_complete/monthly/{month[:4]}/{month[:4]}-{month[4:]}/pageviews-{month}-user.bz2"


def _stream_frwiki(session, url: str) -> dict[str, int]:
    """Vues par titre pour fr.wikipedia, en lisant le fichier bz2 en flux (avec reprise)."""
    views: dict[str, int] = defaultdict(int)
    decompressor = bz2.BZ2Decompressor()
    offset = 0           # octets compressés déjà consommés (pour reprendre après une coupure)
    pending = ""         # fin de ligne incomplète du morceau précédent
    started = False

    for attempt in range(MAX_RESUMES):
        try:
            headers = {"Range": f"bytes={offset}-"} if offset else {}
            with session.get(url, headers=headers, stream=True, timeout=120) as r:
                r.raise_for_status()
                for chunk in r.iter_content(1 << 20):
                    offset += len(chunk)
                    data = decompressor.decompress(chunk)
                    while decompressor.eof:  # fichier composé de plusieurs flux bz2
                        rest = decompressor.unused_data
                        decompressor = bz2.BZ2Decompressor()
                        data += decompressor.decompress(rest) if rest else b""
                        if not rest:
                            break
                    text = pending + data.decode("utf-8", "replace")
                    if not started:
                        # Avant frwiki : simple recherche de chaîne, sans découper en lignes.
                        idx = text.find("\n" + PREFIX)
                        if idx < 0:
                            pending = text[text.rfind("\n") + 1:]
                            continue
                        started, text = True, text[idx + 1:]
                    lines = text.split("\n")
                    pending = lines.pop()
                    for line in lines:
                        if not line.startswith(PREFIX):
                            return views  # bloc frwiki terminé : inutile de lire la suite
                        parts = line.split(" ")
                        if len(parts) >= 5:
                            views[parts[1]] += int(parts[-2])
            return views
        except (requests.ConnectionError, requests.exceptions.ChunkedEncodingError) as e:
            print(f"  connexion coupée ({e.__class__.__name__}), reprise {attempt + 1}/{MAX_RESUMES}")
            time.sleep(min(60, 5 * (attempt + 1)))
    raise RuntimeError(f"lecture impossible : {url}")


def dump_monthly(out_dir: Path | None = None) -> None:
    out_dir = out_dir or work_path("pageviews_dumps")
    out_dir.mkdir(parents=True, exist_ok=True)
    session = make_session()
    for month in months_before_dump():
        path = out_dir / f"{month}.tsv.gz"
        if path.exists():
            print(f"{month} : déjà fait")
            continue
        t0 = time.time()
        views = _stream_frwiki(session, _month_url(month))
        tmp = path.with_name(path.name + ".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            for title, n in views.items():
                f.write(f"{title}\t{n}\n")
        tmp.replace(path)
        print(f"{month} : {len(views):,} pages, {sum(views.values()):,} vues, {(time.time() - t0) / 60:.0f} min",
              flush=True)


def build_pageviews(dumps_dir: Path | None = None) -> None:
    dumps_dir = dumps_dir or work_path("pageviews_dumps")
    months = months_before_dump()
    missing = [m for m in months if not (dumps_dir / f"{m}.tsv.gz").exists()]
    if missing:
        raise RuntimeError(f"mois manquants dans {dumps_dir} : {missing} (lancer lg pageviews-dump)")

    humans = pl.read_parquet(work_path("humans.parquet")).select("qid", "title")
    # Un titre « vu » peut être une redirection : ses vues reviennent à la biographie visée.
    redirects = pl.read_parquet(work_path("redirects.parquet")).join(
        humans.rename({"title": "to_title"}), on="to_title", how="inner").select(pl.col("from_title").alias("title"), "qid")
    title_to_qid = pl.concat([humans, redirects]).unique("title")

    per_month = []
    for m in months:
        df = pl.read_csv(dumps_dir / f"{m}.tsv.gz", separator="\t", has_header=False, quote_char=None,
                         new_columns=["title", "views"], schema_overrides={"title": pl.Utf8, "views": pl.Int64})
        per_month.append(df.join(title_to_qid, on="title", how="inner")
                         .group_by("qid").agg(pl.col("views").sum().alias(m)))
    wide = humans.select("qid")
    for m, df in zip(months, per_month):
        wide = wide.join(df, on="qid", how="left")
    wide = wide.fill_null(0)
    result = wide.select(
        "qid",
        pl.sum_horizontal(months).alias("pageviews_12m"),
        pl.concat_list([pl.col(m).cast(pl.Int32) for m in months]).alias("pageviews_monthly"),
    )
    result.write_parquet(work_path("pageviews.parquet"))
    top = result.join(humans, on="qid").sort("pageviews_12m", descending=True).head(10)
    print(f"{result.height:,} biographies, {result['pageviews_12m'].sum():,} vues sur 12 mois. Top 10 :")
    for r in top.iter_rows(named=True):
        print(f"  {r['title']}: {r['pageviews_12m']:,}")

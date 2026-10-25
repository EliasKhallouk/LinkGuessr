"""Avancement de chaque étape du pipeline, d'après les fichiers déjà produits."""
import math

import polars as pl

from .config import dump_path, work_path
from .download import SQL_DUMPS, XML_DUMPS, _url
from .entities import SHARD
from .http import make_session
from .pageviews import months_before_dump


def _size(path) -> str:
    return f"{path.stat().st_size / 1e9:.2f} Go"


def show_status() -> None:
    print("== Téléchargements")
    session = make_session()
    for suffix in SQL_DUMPS + XML_DUMPS:
        path = dump_path(suffix)
        part = path.with_name(path.name + ".part")
        if path.with_name(path.name + ".ok").exists():
            print(f"  ✅ {suffix}")
        elif part.exists():
            total = int(session.head(_url(path.name), timeout=30).headers.get("Content-Length", 0))
            pct = f" ({100 * part.stat().st_size / total:.0f} %)" if total else ""
            print(f"  ⏳ {suffix} : {_size(part)}{pct}")
        else:
            print(f"  ·  {suffix} : pas commencé")

    def done(name: str) -> bool:
        return work_path(name).exists()

    print("== Étapes")
    print(f"  {'✅' if done('articles.parquet') else '· '} pages")
    if done("humans.parquet"):
        n = pl.scan_parquet(work_path("humans.parquet")).select(pl.len()).collect().item()
        print(f"  ✅ humans : {n:,} personnes")
        shards = math.ceil(n / SHARD)
        got = len(list(work_path("entities_humans").glob("*.jsonl.gz"))) if done("entities_humans") else 0
        print(f"  {'✅' if got == shards else '⏳'} entities : {got}/{shards} fragments ({100 * got / shards:.0f} %)")
    else:
        print("  ·  humans")
    print(f"  {'✅' if done('refs.parquet') or done('entities_refs') else '· '} refs")
    months = months_before_dump()
    got = sum((work_path("pageviews_dumps") / f"{m}.tsv.gz").exists() for m in months)
    print(f"  {'✅' if done('pageviews.parquet') else '· '} pageviews : {got}/12 mois rapatriés de la VM "
          "(avancement sur la VM : journalctl -u linkguessr-pageviews)")
    for step, output in [("links", "text_links.parquet"), ("build", "persons.parquet"), ("graph", "final/graph.npz")]:
        print(f"  {'✅' if done(output) else '· '} {step}")

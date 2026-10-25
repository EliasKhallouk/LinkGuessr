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
    rounds = sorted(work_path("entities_refs").glob("*")) if done("entities_refs") else []
    frags = sum(len(list(r.glob("*.jsonl.gz"))) for r in rounds)
    refs_state = "✅" if done("refs.parquet") else ("⏳" if rounds else "· ")
    print(f"  {refs_state} refs : {frags} fragments téléchargés, {len(rounds)} niveau(x) de hiérarchie"
          if rounds else f"  {refs_state} refs")
    months = months_before_dump()
    pv_dir = work_path("pageviews_dumps")
    sizes = {m: (pv_dir / f"{m}.tsv.gz").stat().st_size for m in months if (pv_dir / f"{m}.tsv.gz").exists()}
    pv_state = "✅" if done("pageviews.parquet") else ("⏳" if sizes else "· ")
    print(f"  {pv_state} pageviews : {len(sizes)}/12 mois présents sur le PC ({sum(sizes.values()) / 1e6:.0f} Mo)")
    for step, output in [("links", "text_links.parquet"), ("build", "persons.parquet"), ("graph", "final/graph.npz")]:
        print(f"  {'✅' if done(output) else '· '} {step}")

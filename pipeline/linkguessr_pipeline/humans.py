"""Sélectionne les articles qui parlent d'un être humain (Wikidata P31 = Q5).

On interroge le SPARQL officiel par lots de QID (VALUES), ce qui évite la
requête globale qui dépasse le délai du serveur. Reprise possible grâce au
fichier de points de contrôle.

Sortie : humans.parquet  qid, page_id, title, length
"""
import csv
import io
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import polars as pl
from tqdm import tqdm

from .config import work_path
from .http import make_session

WDQS = "https://query.wikidata.org/sparql"
BATCH = 4000
ENTITY_PREFIX = "http://www.wikidata.org/entity/"


def find_humans() -> None:
    articles = pl.read_parquet(work_path("articles.parquet")).filter(
        ~pl.col("is_redirect") & pl.col("qid").is_not_null()
    )
    qids = sorted(articles["qid"].unique().to_list())
    batches = [qids[i:i + BATCH] for i in range(0, len(qids), BATCH)]

    checkpoint = work_path("humans_batches.jsonl")
    done: dict[int, list[str]] = {}
    if checkpoint.exists():
        for line in checkpoint.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            done[entry["batch"]] = entry["humans"]

    session = make_session()

    def query(batch: list[str]) -> list[str]:
        values = " ".join(f"wd:{q}" for q in batch)
        sparql = f"SELECT ?item WHERE {{ VALUES ?item {{ {values} }} ?item wdt:P31 wd:Q5 . }}"
        r = session.post(WDQS, data={"query": sparql}, headers={"Accept": "text/csv"}, timeout=120)
        r.raise_for_status()
        rows = list(csv.reader(io.StringIO(r.text)))[1:]
        return [row[0].removeprefix(ENTITY_PREFIX) for row in rows if row]

    pending = [i for i in range(len(batches)) if i not in done]
    # WDQS tolère 5 requêtes simultanées par IP : on reste à 3.
    with checkpoint.open("a", encoding="utf-8") as out, ThreadPoolExecutor(3) as pool:
        futures = {pool.submit(query, batches[i]): i for i in pending}
        for fut in tqdm(as_completed(futures), total=len(futures), desc="WDQS", unit="lot"):
            i = futures[fut]
            done[i] = fut.result()
            out.write(json.dumps({"batch": i, "humans": done[i]}) + "\n")
            out.flush()

    human_qids = pl.DataFrame({"qid": sorted({q for found in done.values() for q in found})})
    humans = articles.join(human_qids, on="qid", how="inner").select("qid", "page_id", "title", "length")
    humans.write_parquet(work_path("humans.parquet"))
    print(f"{humans.height:,} personnes sur {len(qids):,} articles avec QID")

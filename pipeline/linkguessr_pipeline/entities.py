"""Télécharge les entités Wikidata complètes (wbgetentities, lots de 50).

Les entités sont allégées (pas de références, pas de rang « deprecated »,
libellés mul/fr/en seulement) puis écrites en JSONL gzip, par fragments de
SHARD entités : un fragment déjà présent n'est pas re-téléchargé.

Format d'une ligne :
  {"id", "labels": {lang: str}, "descriptions": {lang: str}, "aliases": {lang: [str]},
   "sitelinks": {"count": int, "sites": [str], "frwiki": str, "enwiki": str},
   "claims": {pid: [{"v": valeur, "r": "p" si préféré, "q": {pid: [valeurs]}}]}}
Valeurs : "Q42" (entité), {"t": "+1952-03-11T00:00:00Z", "p": 11} (date),
{"lat", "lon"}, {"amount", "unit"}, {"text", "lang"}, str, ou {"special": "somevalue"|"novalue"}.
"""
import gzip
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import polars as pl
from tqdm import tqdm

from .config import work_path
from .http import make_session

API = "https://www.wikidata.org/w/api.php"
BATCH = 50
SHARD = 2000
# "mul" : libellé commun à plusieurs langues (souvent le seul pour les noms de personnes).
LANGS = "mul|fr|en"
# Sites Wikimedia qui ne sont pas des éditions de Wikipédia.
NON_WIKIPEDIA_SITES = {"commonswiki", "specieswiki", "metawiki", "wikidatawiki", "mediawikiwiki",
                       "sourceswiki", "outreachwiki", "wikimaniawiki", "foundationwiki", "wikifunctionswiki"}
WIKI_PROJECT_SUFFIXES = ("wikiquote", "wikisource", "wikinews", "wikibooks", "wikiversity", "wikivoyage", "wiktionary")


def _value(snak: dict):
    if snak.get("snaktype") != "value":
        return {"special": snak.get("snaktype")}
    dv = snak["datavalue"]
    v, kind = dv["value"], dv["type"]
    if kind == "wikibase-entityid":
        return v["id"]
    if kind == "time":
        return {"t": v["time"], "p": v["precision"]}
    if kind == "globecoordinate":
        return {"lat": v["latitude"], "lon": v["longitude"]}
    if kind == "quantity":
        return {"amount": v["amount"], "unit": v["unit"].rsplit("/", 1)[-1]}
    if kind == "monolingualtext":
        return {"text": v["text"], "lang": v["language"]}
    return v


def _slim(entity: dict, keep_claims: set[str] | None = None) -> dict:
    claims = {}
    for pid, statements in entity.get("claims", {}).items():
        if keep_claims is not None and pid not in keep_claims:
            continue
        kept = []
        for st in statements:
            if st.get("rank") == "deprecated":
                continue
            item = {"v": _value(st["mainsnak"])}
            if st.get("rank") == "preferred":
                item["r"] = "p"
            if quals := st.get("qualifiers"):
                item["q"] = {qp: [_value(s) for s in snaks] for qp, snaks in quals.items()}
            kept.append(item)
        if kept:
            claims[pid] = kept

    sitelinks = entity.get("sitelinks", {})
    wikipedias = [s for s in sitelinks
                  if s.endswith("wiki") and s not in NON_WIKIPEDIA_SITES and not s.endswith(WIKI_PROJECT_SUFFIXES)]
    return {
        "id": entity["id"],
        "labels": {k: v["value"] for k, v in entity.get("labels", {}).items()},
        "descriptions": {k: v["value"] for k, v in entity.get("descriptions", {}).items()},
        "aliases": {k: [a["value"] for a in v] for k, v in entity.get("aliases", {}).items()},
        "sitelinks": {
            "count": len(wikipedias),
            "sites": sorted(sitelinks),
            "frwiki": sitelinks.get("frwiki", {}).get("title"),
            "enwiki": sitelinks.get("enwiki", {}).get("title"),
        },
        "claims": claims,
    }


def _get_batch(session, ids: list[str], props: str) -> dict:
    params = {"action": "wbgetentities", "ids": "|".join(ids), "props": props,
              "languages": LANGS, "format": "json", "formatversion": 2}
    # Pas de maxlag : il sert aux robots qui modifient Wikidata, et il bloquerait souvent nos lectures.
    r = session.get(API, params=params, timeout=120)
    r.raise_for_status()
    data = r.json()
    if error := data.get("error"):
        raise RuntimeError(f"wbgetentities : {error}")
    return data["entities"]


def _fetch_shard(session, qids: list[str], path: Path, props: str, keep_claims: set[str] | None) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        for i in range(0, len(qids), BATCH):
            for entity in _get_batch(session, qids[i:i + BATCH], props).values():
                if "missing" in entity:
                    continue
                f.write(json.dumps(_slim(entity, keep_claims), ensure_ascii=False) + "\n")
    tmp.replace(path)


def fetch_entities(qids: list[str], out_dir: Path, workers: int = 2,
                   props: str = "labels|descriptions|aliases|claims|sitelinks",
                   keep_claims: set[str] | None = None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    qids = sorted(set(qids))
    shards = [(qids[i:i + SHARD], out_dir / f"{i // SHARD:05d}.jsonl.gz") for i in range(0, len(qids), SHARD)]
    pending = [(chunk, path) for chunk, path in shards if not path.exists()]
    print(f"{len(qids):,} entités, {len(shards) - len(pending)}/{len(shards)} fragments déjà faits")

    session = make_session()
    with ThreadPoolExecutor(workers) as pool:
        futures = [pool.submit(_fetch_shard, session, chunk, path, props, keep_claims) for chunk, path in pending]
        for fut in tqdm(as_completed(futures), total=len(futures), desc="wbgetentities", unit="fragment"):
            fut.result()


def fetch_human_entities(workers: int = 2, limit: int | None = None) -> None:
    qids = pl.read_parquet(work_path("humans.parquet"))["qid"].to_list()
    if limit:
        qids = sorted(qids)[:limit]
    fetch_entities(qids, work_path("entities_humans"), workers)


def iter_entities(directory: Path):
    """Relit les entités téléchargées, fragment par fragment (sans tout charger en mémoire)."""
    for path in sorted(directory.glob("*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                yield json.loads(line)

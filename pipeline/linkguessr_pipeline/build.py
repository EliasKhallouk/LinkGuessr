"""Assemble les tables finales à partir des entités Wikidata et du texte des articles.

Sorties (dossier work) :
  persons.parquet    une ligne par personne : la fiche structurée
  facts.parquet      faits datés (fonctions, clubs, prix, formation...)
  relations.parquet  relations Wikidata entre personnes (famille, élève, succession...)
  refs.parquet       libellés et coordonnées des entités citées
"""
import json
import re
from collections import deque

import polars as pl
from tqdm import tqdm

from .config import work_path
from .entities import iter_entities
from .parts import PartWriter
from .refs import load_refs
from .wd_schema import (ANCHOR_TO_DOMAIN, DOMAIN_SIGNALS, EXTERNAL_IDS, FACT_PROPS, GENDERS, RELATION_PROPS,
                        SUCCESSION_QUALIFIERS)

S, I64, L = pl.Utf8, pl.Int64, pl.List(pl.Utf8)
PERSON_SCHEMA = {
    "qid": S, "title": S, "title_en": S, "name": S, "description": S, "aliases": L, "birth_name": S,
    "pseudonyms": L, "gender": S, "birth_year": I64, "birth_date": S, "birth_precision": pl.Int8,
    "death_year": I64, "death_date": S, "death_precision": pl.Int8, "birth_place": S, "birth_country": S,
    "death_place": S, "death_country": S, "citizenships": L, "occupations": L, "domains": L, "primary_domain": S,
    "image": S, "height_cm": pl.Int32, "external_ids": S, "sitelinks": pl.Int16, "article_len": pl.Int32,
}
FACT_SCHEMA = {
    "person_qid": S, "prop": S, "value_qid": S, "start_year": I64, "end_year": I64,
    "start_date": S, "end_date": S, "preferred": pl.Boolean, "qualifiers": S,
}
RELATION_SCHEMA = {
    "source_qid": S, "target_qid": S, "prop": S, "family": S, "label": S, "context_qid": S,
    "start_year": I64, "end_year": I64,
}

_TIME = re.compile(r"([+-])(\d+)-(\d\d)-(\d\d)")


def parse_time(v) -> dict | None:
    """{"t": "+1977-12-21T00:00:00Z", "p": 11} -> année, date ISO (si précision au jour), précision."""
    if not isinstance(v, dict) or "t" not in v:
        return None
    m = _TIME.match(v["t"])
    if not m:
        return None
    sign, year, month, day = m.groups()
    year = int(year) * (-1 if sign == "-" else 1)
    precision = v["p"]
    date = f"{year:04d}-{month}-{day}" if precision >= 11 and year > 0 and month != "00" and day != "00" else None
    return {"year": year, "date": date, "precision": precision}


def _best(statements: list[dict]) -> list[dict]:
    """Rang « préféré » s'il existe, sinon toutes les affirmations normales."""
    preferred = [s for s in statements if s.get("r") == "p"]
    return preferred or statements


def _first_value(claims: dict, pid: str):
    for st in _best(claims.get(pid, [])):
        if not isinstance(st["v"], dict) or "special" not in st["v"]:
            return st["v"]
    return None


def _qualifier_time(st: dict, pid: str) -> dict | None:
    for v in st.get("q", {}).get(pid, []):
        if t := parse_time(v):
            return t
    return None


def _label(entity: dict | None) -> str | None:
    if not entity:
        return None
    labels = entity.get("labels", {})
    return labels.get("fr") or labels.get("mul") or labels.get("en")


class DomainResolver:
    """Domaine d'une profession = domaine de la profession racine la plus proche via P279."""

    def __init__(self, refs: dict[str, dict]):
        self.refs = refs
        self.cache: dict[str, set[str]] = {}

    def __call__(self, occupation: str) -> set[str]:
        if occupation in self.cache:
            return self.cache[occupation]
        found: set[str] = set()
        seen = {occupation}
        queue = deque([(occupation, 0)])
        best_depth = None
        while queue:
            q, depth = queue.popleft()
            if best_depth is not None and depth > best_depth:
                break
            if q in ANCHOR_TO_DOMAIN:
                found.add(ANCHOR_TO_DOMAIN[q])
                best_depth = depth
                continue
            for st in self.refs.get(q, {}).get("claims", {}).get("P279", []):
                parent = st["v"]
                if isinstance(parent, str) and parent not in seen and depth < 8:
                    seen.add(parent)
                    queue.append((parent, depth + 1))
        self.cache[occupation] = found
        return found


def build() -> None:
    humans = pl.read_parquet(work_path("humans.parquet"))
    human_qids = set(humans["qid"].to_list())
    article_len = dict(zip(humans["qid"].to_list(), humans["length"].to_list()))
    refs = load_refs()
    domain_of = DomainResolver(refs)

    def country_of(place) -> str | None:
        return _first_value(refs[place]["claims"], "P17") if isinstance(place, str) and place in refs else None

    persons = PartWriter(work_path("parts_persons"), PERSON_SCHEMA)
    facts = PartWriter(work_path("parts_facts"), FACT_SCHEMA)
    relations = PartWriter(work_path("parts_relations"), RELATION_SCHEMA)
    for e in tqdm(iter_entities(work_path("entities_humans")), total=len(human_qids), desc="fiches", unit=" pers."):
        qid, claims = e["id"], e["claims"]
        if qid not in human_qids:
            continue
        labels, descs = e["labels"], e["descriptions"]

        birth = parse_time(_first_value(claims, "P569")) or {}
        death = parse_time(_first_value(claims, "P570")) or {}
        occupations = [st["v"] for st in claims.get("P106", []) if isinstance(st["v"], str)]
        # Domaines triés par nombre de professions qui y mènent (le premier = domaine principal).
        domain_votes: dict[str, int] = {}
        for occ in occupations:
            for d in sorted(domain_of(occ)):
                domain_votes[d] = domain_votes.get(d, 0) + 1
        from_occupations = bool(domain_votes)
        for d in {d for pid, d in DOMAIN_SIGNALS.items() if pid in claims}:
            if d in domain_votes or not from_occupations:
                domain_votes[d] = domain_votes.get(d, 0) + 1
        domains = sorted(domain_votes, key=lambda d: -domain_votes[d])
        birth_place, death_place = _first_value(claims, "P19"), _first_value(claims, "P20")
        height = _first_value(claims, "P2048")
        externals = {name: v for pid, name in EXTERNAL_IDS.items() if isinstance(v := _first_value(claims, pid), str)}
        title = e["sitelinks"]["frwiki"]

        persons.add({
            "qid": qid,
            "title": title.replace(" ", "_") if title else None,
            "title_en": e["sitelinks"]["enwiki"],
            "name": labels.get("fr") or labels.get("mul") or re.sub(r"\s*\(.*\)$", "", title or "") or labels.get("en"),
            "description": descs.get("fr") or descs.get("en"),
            "aliases": sorted(set(e["aliases"].get("fr", []) + e["aliases"].get("mul", []))),
            "birth_name": birth_name.get("text") if isinstance(birth_name := _first_value(claims, "P1477"), dict) else None,
            "pseudonyms": [v if isinstance(v := st["v"], str) else v.get("text") for st in claims.get("P742", [])
                           if isinstance(st["v"], str) or "text" in st["v"]],
            "gender": GENDERS.get(_first_value(claims, "P21")),
            "birth_year": birth.get("year"), "birth_date": birth.get("date"), "birth_precision": birth.get("precision"),
            "death_year": death.get("year"), "death_date": death.get("date"), "death_precision": death.get("precision"),
            "birth_place": birth_place if isinstance(birth_place, str) else None,
            "birth_country": country_of(birth_place),
            "death_place": death_place if isinstance(death_place, str) else None,
            "death_country": country_of(death_place),
            "citizenships": [st["v"] for st in _best(claims.get("P27", [])) if isinstance(st["v"], str)],
            "occupations": occupations,
            "domains": domains,
            "primary_domain": domains[0] if domains else None,
            "image": image if isinstance(image := _first_value(claims, "P18"), str) else None,
            "height_cm": round(float(height["amount"]) * 100) if isinstance(height, dict) and height.get("unit") == "Q11573" else None,
            "external_ids": json.dumps(externals, ensure_ascii=False) if externals else None,
            "sitelinks": e["sitelinks"]["count"],
            "article_len": article_len.get(qid),
        })

        for pid in FACT_PROPS:
            for st in claims.get(pid, []):
                if not isinstance(st["v"], str):
                    continue
                start, end, when = (_qualifier_time(st, p) for p in ("P580", "P582", "P585"))
                quals = {k: v for k, v in st.get("q", {}).items() if k not in ("P580", "P582", "P585")}
                facts.add({
                    "person_qid": qid, "prop": pid, "value_qid": st["v"],
                    "start_year": (start or when or {}).get("year"), "end_year": (end or when or {}).get("year"),
                    "start_date": (start or when or {}).get("date"), "end_date": (end or when or {}).get("date"),
                    "preferred": st.get("r") == "p",
                    "qualifiers": json.dumps(quals, ensure_ascii=False) if quals else None,
                })
                if pid == "P39":
                    for qp, kind in SUCCESSION_QUALIFIERS.items():
                        for other in st.get("q", {}).get(qp, []):
                            if isinstance(other, str) and other in human_qids and other != qid:
                                relations.add({
                                    "source_qid": qid, "target_qid": other, "prop": qp, "family": "succession",
                                    "label": kind, "context_qid": st["v"],
                                    "start_year": (start or {}).get("year"), "end_year": (end or {}).get("year"),
                                })

        for pid, meta in RELATION_PROPS.items():
            for st in claims.get(pid, []):
                other = st["v"]
                if isinstance(other, str) and other in human_qids and other != qid:
                    start, end = _qualifier_time(st, "P580"), _qualifier_time(st, "P582")
                    relations.add({
                        "source_qid": qid, "target_qid": other, "prop": pid, "family": meta["family"],
                        "label": meta["label"], "context_qid": None,
                        "start_year": (start or {}).get("year"), "end_year": (end or {}).get("year"),
                    })

    extras = [work_path(f) for f in ("pages_text.parquet", "pageviews.parquet") if work_path(f).exists()]

    def with_extras(frame: pl.LazyFrame) -> pl.LazyFrame:
        for extra in extras:
            frame = frame.join(pl.scan_parquet(extra), on="qid", how="left")
        return frame

    n_persons = persons.finish(work_path("persons.parquet"), with_extras)
    n_facts = facts.finish(work_path("facts.parquet"))
    n_relations = relations.finish(work_path("relations.parquet"), lambda f: f.unique())

    refs_rows = []
    for q, ent in refs.items():
        coord = _first_value(ent["claims"], "P625")
        refs_rows.append({
            "qid": q, "label": _label(ent), "description": ent["descriptions"].get("fr") or ent["descriptions"].get("en"),
            "lat": coord.get("lat") if isinstance(coord, dict) else None,
            "lon": coord.get("lon") if isinstance(coord, dict) else None,
            "country_qid": _first_value(ent["claims"], "P17"),
            "instance_of": [st["v"] for st in ent["claims"].get("P31", []) if isinstance(st["v"], str)],
        })
    pl.DataFrame(refs_rows, infer_schema_length=None).write_parquet(work_path("refs.parquet"), compression="zstd")
    print(f"{n_persons:,} fiches, {n_facts:,} faits, {n_relations:,} relations (avant dédoublonnage), "
          f"{len(refs_rows):,} références")

"""Entités de référence citées par les fiches : lieux, professions, partis, clubs, prix...

On télécharge leurs libellés et quelques propriétés (REF_CLAIMS), puis on remonte
la hiérarchie « sous-classe de » (P279) des professions pour pouvoir les classer
en domaines. Chaque niveau de remontée est un « tour » stocké dans son propre dossier.
"""
from pathlib import Path

import polars as pl

from .config import work_path
from .entities import fetch_entities, iter_entities
from .wd_schema import FACT_PROPS, QUALIFIER_PROPS, REF_CLAIMS

REFS_DIR_NAME = "entities_refs"
MAX_P279_DEPTH = 8


def _is_qid(v) -> bool:
    return isinstance(v, str) and v.startswith("Q")


def _collect_from_humans(humans: set[str]) -> tuple[set[str], set[str]]:
    refs, occupations = set(), set()
    for e in iter_entities(work_path("entities_humans")):
        claims = e["claims"]
        for pid in FACT_PROPS.keys() | {"P19", "P20", "P21"}:
            for st in claims.get(pid, []):
                if _is_qid(st["v"]):
                    refs.add(st["v"])
                    if pid == "P106":
                        occupations.add(st["v"])
                for qp, values in st.get("q", {}).items():
                    if qp in QUALIFIER_PROPS:
                        refs.update(v for v in values if _is_qid(v))
    return refs - humans, occupations


def refs_dirs() -> list[Path]:
    root = work_path(REFS_DIR_NAME)
    return sorted((p for p in root.glob("*") if p.is_dir()), key=lambda p: int(p.name)) if root.exists() else []


def load_refs() -> dict[str, dict]:
    return {e["id"]: e for d in refs_dirs() for e in iter_entities(d)}


def fetch_refs(workers: int = 2) -> None:
    humans = set(pl.read_parquet(work_path("humans.parquet"))["qid"].to_list())
    refs, occupations = _collect_from_humans(humans)
    print(f"{len(refs):,} entités de référence, dont {len(occupations):,} professions")
    root = work_path(REFS_DIR_NAME)
    fetch_entities(sorted(refs), root / "0", workers, props="labels|descriptions|claims", keep_claims=REF_CLAIMS)

    known = load_refs()
    frontier = occupations
    for depth in range(1, MAX_P279_DEPTH + 1):
        parents = {st["v"] for q in frontier if q in known
                   for st in known[q]["claims"].get("P279", []) if _is_qid(st["v"])}
        missing = parents - known.keys()
        if not parents:
            break
        if missing:
            print(f"P279 niveau {depth} : {len(missing):,} classes à télécharger")
            fetch_entities(sorted(missing), root / str(depth), workers,
                           props="labels|descriptions|claims", keep_claims=REF_CLAIMS)
            known.update({e["id"]: e for e in iter_entities(root / str(depth))})
        frontier = parents

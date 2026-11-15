"""Pré-annotation par lots : affiche les phrases hors accord sans proposition, dans un format compact.

Les propositions sont écrites à la main par le LLM dans annotation/suggestions.jsonl
({"ordre", "labels", "cotoyes", "wrong"?}), puis chargées sur la VM (python -m app.annotation suggest).
Reprise : les phrases déjà présentes dans suggestions.jsonl ne sont plus proposées.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def paths(dump: str) -> tuple[Path, Path]:
    d = ROOT / "pipeline" / "data" / "lab" / dump / "annotation"
    return d / "items.jsonl", d / "suggestions.jsonl"


def next_batch(dump: str = "20261001", size: int = 50) -> None:
    items_path, sugg_path = paths(dump)
    done = set()
    if sugg_path.exists():
        done = {json.loads(l)["ordre"] for l in sugg_path.read_text(encoding="utf-8").splitlines() if l.strip()}
    todo = [it for it in map(json.loads, items_path.read_text(encoding="utf-8").splitlines())
            if not it["accord"] and it["ordre"] not in done]
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"# {len(done)} faites, {len(todo)} restantes")
    for it in todo[:size]:
        life = "" if it["vies_chevauchent"] is not False else " [vies disjointes]"
        print(f"{it['ordre']} | {it['a_name']} ({it['a_birth_year']}-{it['a_death_year']}) -> "
              f"{it['b_name']} ({it['b_birth_year']}-{it['b_death_year']}){life} | {it['kind']} | "
              f"{it['section']} | {it['sentence']}")

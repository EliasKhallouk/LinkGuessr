"""Jeu de données d'entraînement : annotations (exportées de la VM) + phrases du tirage → dataset.parquet.

Découpage (colonne `split`), calculé sur les 1 500 phrases tirées et non sur celles déjà annotées, pour qu'une
phrase ne change jamais de partie au fil de l'annotation :
  test   les 300 phrases de l'accord (annotées à l'aveugle), examen final ;
  val    ~15 % des autres, pour régler les modèles ;
  train  le reste, pour apprendre ;
  exclu  phrases qui partagent une personne avec le test (sinon le test n'est plus « jamais vu »).
Le découpage se fait par groupe de personnes reliées (union-find) : deux phrases qui partagent une personne
tombent toujours dans la même partie.

Deux versions de la phrase :
  texte_masque  noms de A et B remplacés par [A] et [B] : le modèle ne peut pas apprendre « Curie → couple » ;
  texte_balise  noms gardés et entourés : [A]Pierre Curie[/A]. Comparer les deux mesure l'effet des noms.
"""
import json
import re
from pathlib import Path

import numpy as np
import polars as pl

from .grille import COTOYES, LABELS

ROOT = Path(__file__).resolve().parents[3]
SEED = 20261115
VAL_SHARE = 0.15
ANNOTATOR = "elias"  # annotateur de référence pour train et val


def annotation_dir(dump: str) -> Path:
    return ROOT / "pipeline" / "data" / "lab" / dump / "annotation"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


# --- Noms : variantes, masquage, balisage ------------------------------------------------------

def variants(name: str | None) -> list[str]:
    """Formes du nom cherchées dans la phrase : nom complet sans parenthèse, et nom de famille (comme la page)."""
    full = re.sub(r"\s*\([^)]*\)$", "", name or "").strip()
    words = full.split()
    out = [full] if full else []
    if len(words) > 1 and len(words[-1]) >= 4 and not re.fullmatch(r"[IVXLC]+|Ier", words[-1]):
        out.append(words[-1])
    return out


def mark(sentence: str, a_name: str | None, b_name: str | None, masque: bool) -> tuple[str, bool, bool]:
    """Remplace (masque) ou entoure (balise) les noms de A et B. Renvoie le texte et si A, B ont été trouvés."""
    forms: dict[str, str] = {}
    for role, name in (("B", b_name), ("A", a_name)):
        for v in {w for v in variants(name) for w in (v, v.replace("'", "’"), v.replace("’", "'"))}:
            # Même forme pour les deux (Pierre et Marie Curie → « Curie ») : ambiguë, on ne la touche pas.
            forms[v] = "?" if forms.get(v, role) != role else role
    forms = {v: r for v, r in forms.items() if r != "?"}
    if not forms:
        return sentence, False, False
    # Une seule expression, formes les plus longues d'abord : « Marie Curie » passe avant « Curie ».
    pattern = re.compile(r"(?<![\w-])(" + "|".join(map(re.escape, sorted(forms, key=len, reverse=True))) + r")(?![\w-])")
    found = set()

    def repl(m: re.Match) -> str:
        role = forms[m.group(1)]
        found.add(role)
        return f"[{role}]" if masque else f"[{role}]{m.group(1)}[/{role}]"

    return pattern.sub(repl, sentence), "A" in found, "B" in found


# --- Découpage ---------------------------------------------------------------------------------

def split_items(items: list[dict]) -> dict[int, str]:
    """Partie de chaque phrase (ordre → train / val / test / exclu), stable et reproductible."""
    test_people = {q for it in items if it["accord"] for q in (it["source_qid"], it["target_qid"])}
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # compression de chemin
            x = parent[x]
        return x

    rest = [it for it in items if not it["accord"]]
    for it in rest:
        parent[find(it["source_qid"])] = find(it["target_qid"])
    groups: dict[str, list[dict]] = {}
    for it in rest:
        groups.setdefault(find(it["source_qid"]), []).append(it)

    out = {it["ordre"]: "test" for it in items if it["accord"]}
    keep = []
    for g in groups.values():
        if any(q in test_people for it in g for q in (it["source_qid"], it["target_qid"])):
            out.update({it["ordre"]: "exclu" for it in g})
        else:
            keep.append(g)
    keep.sort(key=lambda g: min(it["ordre"] for it in g))  # ordre fixe avant le mélange
    rng = np.random.default_rng(SEED)
    n_val, target = 0, VAL_SHARE * sum(map(len, keep))
    for i in rng.permutation(len(keep)):
        part = "val" if n_val < target else "train"
        n_val += len(keep[i]) if part == "val" else 0
        out.update({it["ordre"]: part for it in keep[i]})
    return out


# --- Construction ------------------------------------------------------------------------------

def gold_labels(annotations: list[dict], arbitrage: list[dict]) -> dict[int, dict]:
    """Réponse de référence par phrase : l'arbitrage s'il existe, sinon l'annotateur de référence."""
    gold = {a["ordre"]: {**a, "origine": ANNOTATOR} for a in annotations if a["annotator"] == ANNOTATOR}
    gold.update({a["ordre"]: {**a, "origine": "arbitrage"} for a in arbitrage})
    return gold


def build(dump: str = "20261001") -> pl.DataFrame:
    d = annotation_dir(dump)
    items = read_jsonl(d / "items.jsonl")
    annotations = read_jsonl(d / "annotations.jsonl")
    arbitrage = read_jsonl(d / "arbitrage.jsonl") if (d / "arbitrage.jsonl").exists() else []
    split = split_items(items)
    gold = gold_labels(annotations, arbitrage)

    rows = []
    for it in items:
        g = gold.get(it["ordre"])
        if g is None or g.get("wrong"):
            continue  # pas encore annotée, ou mauvaise personne : rien à apprendre
        masque, a_ok, b_ok = mark(it["sentence"], it["a_name"], it["b_name"], masque=True)
        balise, _, _ = mark(it["sentence"], it["a_name"], it["b_name"], masque=False)
        labels = list(g["labels"])
        rows.append({
            "ordre": it["ordre"], "split": split[it["ordre"]], "origine": g["origine"],
            "strate": it["strate"], "poids": it["poids"], "kind": it["kind"], "section": it["section"],
            "sentence": it["sentence"], "texte_masque": masque, "texte_balise": balise,
            "a_trouve": a_ok, "b_trouve": b_ok, "a_name": it["a_name"], "b_name": it["b_name"],
            "vies_chevauchent": it["vies_chevauchent"],
            "labels": labels, **{f"y_{l}": l in labels for l in LABELS},
            "cotoyes": g["cotoyes"], "doute": bool(g.get("doubt")),
        })
    df = pl.DataFrame(rows)
    df.write_parquet(d / "dataset.parquet")
    return df


def run(dump: str = "20261001") -> None:
    df = build(dump)
    d = annotation_dir(dump)
    n_wrong = sum(1 for a in read_jsonl(d / "annotations.jsonl") if a["annotator"] == ANNOTATOR and a["wrong"])
    print(f"{len(df)} phrases annotées utilisables ({n_wrong} « mauvaise personne » écartées) -> {d / 'dataset.parquet'}")
    if df.is_empty():
        return
    print(df.group_by("split").len().sort("split"))
    print(f"A trouvé dans la phrase : {df['a_trouve'].mean():.0%}, B trouvé : {df['b_trouve'].mean():.0%}")
    counts = {l: int(df[f"y_{l}"].sum()) for l in LABELS}
    print("Types :", ", ".join(f"{l} {n}" for l, n in sorted(counts.items(), key=lambda x: -x[1])))
    print("Côtoyés :", ", ".join(f"{c} {int((df['cotoyes'] == c).sum())}" for c in COTOYES))

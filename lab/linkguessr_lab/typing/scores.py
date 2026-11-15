"""Scores communs aux trois modèles (mots-clés, CamemBERT, LLM local), calculés de la même façon pour tous.

Les types sont multi-étiquettes : chaque type est une question oui/non posée à chaque phrase. Par type :
  précision = parmi les phrases où le modèle coche le type, part de bonnes réponses   tp / (tp + fp)
  rappel    = parmi les phrases qui ont vraiment ce type, part trouvée par le modèle  tp / (tp + fn)
  F1        = moyenne harmonique des deux                                            2pr / (p + r)
Puis deux moyennes :
  micro  on additionne tp, fp, fn de tous les types : dominé par les types fréquents ;
  macro  moyenne des F1 par type (ceux présents dans la vérité) : chaque type compte autant, les rares aussi.
Avec `weights` (poids du tirage), chaque phrase compte pour les phrases de sa strate : on estime alors le score
sur l'ensemble des 6 M phrases et non sur l'échantillon.

Format des prédictions (un fichier JSONL, une ligne par phrase) : {"ordre", "labels": [...], "cotoyes": "..."}.
"""
import json
from pathlib import Path

import numpy as np
import polars as pl

from .grille import COTOYES, FAMILIES, FAMILY_OF, LABELS


def multi_hot(label_sets: list[list[str]], names: list[str] = LABELS) -> np.ndarray:
    index = {l: i for i, l in enumerate(names)}
    y = np.zeros((len(label_sets), len(names)), dtype=bool)
    for row, labels in enumerate(label_sets):
        for l in labels:
            y[row, index[l]] = True
    return y


def prf(y_true: np.ndarray, y_pred: np.ndarray, names: list[str], w: np.ndarray | None = None) -> dict:
    """Précision, rappel, F1 par colonne, puis micro et macro."""
    w = np.ones(len(y_true)) if w is None else np.asarray(w, dtype=float)
    wc = w[:, None]
    tp = (wc * (y_true & y_pred)).sum(0)
    fp = (wc * (~y_true & y_pred)).sum(0)
    fn = (wc * (y_true & ~y_pred)).sum(0)

    def f(tp, fp, fn):
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        return p, r, (2 * p * r / (p + r) if p + r else 0.0)

    per = {}
    for i, name in enumerate(names):
        p, r, f1 = f(tp[i], fp[i], fn[i])
        per[name] = {"precision": p, "rappel": r, "f1": f1, "support": int(y_true[:, i].sum())}
    present = [n for n in names if per[n]["support"] > 0]
    return {
        "par_type": per,
        "micro_f1": f(tp.sum(), fp.sum(), fn.sum())[2],
        "macro_f1": float(np.mean([per[n]["f1"] for n in present])) if present else 0.0,
    }


def to_families(label_sets: list[list[str]]) -> list[list[str]]:
    return [sorted({FAMILY_OF[l] for l in labels}) for labels in label_sets]


def score(true_labels: list[list[str]], pred_labels: list[list[str]],
          true_coto: list[str | None] | None = None, pred_coto: list[str | None] | None = None,
          weights=None) -> dict:
    y_true, y_pred = multi_hot(true_labels), multi_hot(pred_labels)
    out = {
        "n": len(true_labels),
        "types": prf(y_true, y_pred, LABELS, weights),
        "familles": prf(multi_hot(to_families(true_labels), list(FAMILIES)),
                        multi_hot(to_families(pred_labels), list(FAMILIES)), list(FAMILIES), weights),
        # Par phrase : réponse exactement juste, et recouvrement moyen (Jaccard = |vrai ∩ prédit| / |vrai ∪ prédit|).
        "exact": float(np.mean([set(t) == set(p) for t, p in zip(true_labels, pred_labels)])),
        "jaccard": float(np.mean([len(set(t) & set(p)) / len(set(t) | set(p)) if set(t) | set(p) else 1.0
                                  for t, p in zip(true_labels, pred_labels)])),
    }
    if true_coto is not None and pred_coto is not None:
        pairs = [(t, p) for t, p in zip(true_coto, pred_coto) if t in COTOYES]
        t = np.array([COTOYES.index(a) for a, _ in pairs])
        p = np.array([COTOYES.index(b) if b in COTOYES else -1 for _, b in pairs])
        conf = [[int(((t == i) & (p == j)).sum()) for j in range(3)] for i in range(3)]
        out["cotoyes"] = {
            "exactitude": float((t == p).mean()) if len(t) else 0.0,
            # Réponse absente (-1) : la 4e ligne de eye(4), coupée par [:, :3], ne coche rien.
            "macro_f1": prf(np.eye(3, dtype=bool)[t], np.eye(4, dtype=bool)[p][:, :3], COTOYES)["macro_f1"],
            "confusion (lignes = vrai : non, incertain, oui)": conf,
        }
    return out


def report(s: dict) -> str:
    """Tableau lisible (Markdown) d'un résultat de score()."""
    lines = [f"{s['n']} phrases · F1 micro {s['types']['micro_f1']:.3f} · F1 macro {s['types']['macro_f1']:.3f} · "
             f"familles F1 macro {s['familles']['macro_f1']:.3f} · exact {s['exact']:.3f} · Jaccard {s['jaccard']:.3f}",
             "", "| type | précision | rappel | F1 | support |", "|---|---|---|---|---|"]
    for name, m in sorted(s["types"]["par_type"].items(), key=lambda x: -x[1]["support"]):
        lines.append(f"| {name} | {m['precision']:.2f} | {m['rappel']:.2f} | {m['f1']:.2f} | {m['support']} |")
    if "cotoyes" in s:
        c = s["cotoyes"]
        lines.append(f"\nCôtoyés : exactitude {c['exactitude']:.3f}, F1 macro {c['macro_f1']:.3f}")
    return "\n".join(lines)


def run(dump: str, predictions: Path, split: str = "val", weighted: bool = False) -> dict:
    """Note un fichier de prédictions sur une partie du jeu de données (val par défaut ; test seulement à la fin)."""
    from .dataset import annotation_dir
    df = pl.read_parquet(annotation_dir(dump) / "dataset.parquet").filter(pl.col("split") == split)
    pred = {p["ordre"]: p for p in map(json.loads, predictions.read_text(encoding="utf-8").splitlines()) if p}
    missing = [o for o in df["ordre"] if o not in pred]
    if missing:
        raise SystemExit(f"{len(missing)} phrases de « {split} » sans prédiction (ex. {missing[:5]})")
    rows = df.to_dicts()
    s = score([r["labels"] for r in rows], [pred[r["ordre"]]["labels"] for r in rows],
              [r["cotoyes"] for r in rows], [pred[r["ordre"]].get("cotoyes") for r in rows],
              weights=[r["poids"] for r in rows] if weighted else None)
    print(report(s))
    return s

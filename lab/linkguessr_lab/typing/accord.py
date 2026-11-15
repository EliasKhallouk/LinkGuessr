"""Accord entre les deux annotateurs sur les 300 phrases de l'accord (annotées à l'aveugle).

κ de Cohen = (p_o − p_e) / (1 − p_e) : p_o accord observé, p_e accord attendu si chacun cochait au hasard avec
ses propres fréquences. Le pourcentage d'accord brut est trompeur sur les types rares (deux « non » sur 290
phrases font 97 % d'accord, même sans jamais s'entendre sur les « oui ») ; κ retire cette part de hasard.

Mesures :
  κ par type       chaque type = question oui/non sur chaque phrase
  κ par famille    les types regroupés : montre si les désaccords restent à l'intérieur d'une famille
  α MASI           α de Krippendorff avec la distance MASI (Passonneau 2006) : accord partiel entre ensembles
  côtoyés          κ simple, et κ pondéré (oui contre incertain coûte moitié moins que oui contre non)
Intervalles de confiance à 95 % par bootstrap : on retire 300 phrases parmi les 300 avec remise, 1 000 fois.
Les phrases marquées « mauvaise personne » par l'un des deux sont comptées à part et écartées.
"""
import json
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.metrics import cohen_kappa_score

from .dataset import annotation_dir, read_jsonl
from .grille import COTOYES, FAMILIES, FAMILY_OF, LABELS
from .scores import multi_hot

SEED = 20261115
N_BOOT = 1000


def kappa(a: np.ndarray, b: np.ndarray, weights: str | None = None, labels=None) -> float:
    """κ de Cohen ; NaN quand il n'est pas défini (les deux n'ont jamais coché, p_e = 1)."""
    if len(set(a.tolist()) | set(b.tolist())) < 2:
        return float("nan")
    return float(cohen_kappa_score(a, b, weights=weights, labels=labels))


def masi(a: frozenset, b: frozenset) -> float:
    """Ressemblance MASI : Jaccard × un facteur selon le cas (identiques 1, l'un inclus dans l'autre 2/3,
    simple recouvrement 1/3, rien en commun 0)."""
    if not a and not b:
        return 1.0
    inter = a & b
    m = 1 if a == b else 2 / 3 if a <= b or b <= a else 1 / 3 if inter else 0
    return len(inter) / len(a | b) * m


def alpha_masi(sets_a: list[frozenset], sets_b: list[frozenset]) -> float:
    """α de Krippendorff pour deux annotateurs sans valeur manquante : 1 − désaccord observé / désaccord attendu.
    Le désaccord attendu compare toutes les paires de réponses mélangées, quel que soit l'annotateur."""
    d_obs = np.mean([1 - masi(a, b) for a, b in zip(sets_a, sets_b)])
    counts = Counter(sets_a + sets_b)  # peu d'ensembles distincts : on travaille sur leurs effectifs
    values, n = list(counts), len(sets_a) * 2
    d_exp = sum(counts[u] * counts[v] * (1 - masi(u, v)) for u in values for v in values) / (n * (n - 1))
    return float(1 - d_obs / d_exp) if d_exp else float("nan")


def measures(la: list[list[str]], lb: list[list[str]], ca: list[str], cb: list[str]) -> dict:
    ya, yb = multi_hot(la), multi_hot(lb)
    fam_a = multi_hot([[FAMILY_OF[l] for l in s] for s in la], list(FAMILIES))
    fam_b = multi_hot([[FAMILY_OF[l] for l in s] for s in lb], list(FAMILIES))
    per_type = {l: kappa(ya[:, i], yb[:, i]) for i, l in enumerate(LABELS)}
    per_fam = {f: kappa(fam_a[:, i], fam_b[:, i]) for i, f in enumerate(FAMILIES)}
    coto = [(x, y) for x, y in zip(ca, cb) if x in COTOYES and y in COTOYES]
    xa = np.array([COTOYES.index(x) for x, _ in coto])
    xb = np.array([COTOYES.index(y) for _, y in coto])
    return {
        "accord_exact": float(np.mean([set(x) == set(y) for x, y in zip(la, lb)])),
        "kappa_macro_types": float(np.nanmean(list(per_type.values()))),
        "kappa_macro_familles": float(np.nanmean(list(per_fam.values()))),
        "alpha_masi": alpha_masi([frozenset(s) for s in la], [frozenset(s) for s in lb]),
        "kappa_cotoyes": kappa(xa, xb, labels=[0, 1, 2]),
        "kappa_cotoyes_pondere": kappa(xa, xb, weights="linear", labels=[0, 1, 2]),
        "kappa_types": per_type,
        "kappa_familles": per_fam,
    }


def bootstrap(la, lb, ca, cb, n_boot: int = N_BOOT) -> dict:
    """Intervalle à 95 % (percentiles 2,5 et 97,5) de chaque mesure."""
    rng = np.random.default_rng(SEED)
    samples = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(la), len(la))
        samples.append(measures([la[i] for i in idx], [lb[i] for i in idx], [ca[i] for i in idx], [cb[i] for i in idx]))

    def ci(values):
        v = np.array(values, dtype=float)
        v = v[~np.isnan(v)]
        return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if len(v) else [float("nan")] * 2

    out = {k: ci([s[k] for s in samples]) for k, v in samples[0].items() if not isinstance(v, dict)}
    out["kappa_types"] = {l: ci([s["kappa_types"][l] for s in samples]) for l in LABELS}
    out["kappa_familles"] = {f: ci([s["kappa_familles"][f] for s in samples]) for f in FAMILIES}
    return out


def confusions(la: list[list[str]], lb: list[list[str]]) -> Counter:
    """Couples (type de A, type de B) sur les phrases en désaccord ; « ∅ » quand l'un n'a rien en plus."""
    c = Counter()
    for x, y in zip(la, lb):
        only_a, only_b = set(x) - set(y), set(y) - set(x)
        for u in only_a or {"∅"}:
            for v in only_b or {"∅"}:
                if (u, v) != ("∅", "∅"):
                    c[(u, v)] += 1
    return c


def run(dump: str = "20261001", a: str = "elias", b: str = "annot2") -> dict:
    d = annotation_dir(dump)
    items = {it["ordre"]: it for it in read_jsonl(d / "items.jsonl")}
    ann = {(x["ordre"], x["annotator"]): x for x in read_jsonl(d / "annotations.jsonl") if x["accord"]}
    both = sorted(o for o, who in ann if who == a and (o, b) in ann)
    wrong = [o for o in both if ann[(o, a)]["wrong"] or ann[(o, b)]["wrong"]]
    wrong_both = [o for o in wrong if ann[(o, a)]["wrong"] and ann[(o, b)]["wrong"]]
    kept = [o for o in both if o not in wrong]
    print(f"{len(both)} phrases annotées par {a} et {b} ; « mauvaise personne » : {len(wrong)} "
          f"(dont {len(wrong_both)} par les deux) ; {len(kept)} gardées")
    if len(kept) < 10:
        raise SystemExit("Trop peu de phrases en commun pour mesurer l'accord.")

    la = [ann[(o, a)]["labels"] for o in kept]
    lb = [ann[(o, b)]["labels"] for o in kept]
    ca = [ann[(o, a)]["cotoyes"] for o in kept]
    cb = [ann[(o, b)]["cotoyes"] for o in kept]
    m, ci = measures(la, lb, ca, cb), bootstrap(la, lb, ca, cb)
    conf = confusions(la, lb)

    fmt = lambda v, c: f"{v:.2f} [{c[0]:.2f} ; {c[1]:.2f}]"
    print(f"Accord exact (mêmes types) : {m['accord_exact']:.0%}")
    for k in ("kappa_macro_types", "kappa_macro_familles", "alpha_masi", "kappa_cotoyes", "kappa_cotoyes_pondere"):
        print(f"{k:24} {fmt(m[k], ci[k])}")
    print("\n| type | κ [IC 95 %] | phrases cochées (a / b) |\n|---|---|---|")
    ya, yb = multi_hot(la), multi_hot(lb)
    for i, l in enumerate(LABELS):
        print(f"| {l} | {fmt(m['kappa_types'][l], ci['kappa_types'][l])} | {ya[:, i].sum()} / {yb[:, i].sum()} |")
    print("\nConfusions les plus fréquentes (a coche → b coche) :")
    for (u, v), n in conf.most_common(10):
        print(f"  {n:3}  {u} → {v}")

    # Désaccords à arbitrer ensemble : le résultat arbitré (arbitrage.jsonl) devient le jeu de test.
    disagreements = [
        {"ordre": o, "sentence": items[o]["sentence"], "a_name": items[o]["a_name"], "b_name": items[o]["b_name"],
         a: {k: ann[(o, a)][k] for k in ("labels", "cotoyes", "wrong", "comment")},
         b: {k: ann[(o, b)][k] for k in ("labels", "cotoyes", "wrong", "comment")}}
        for o in both
        if (set(ann[(o, a)]["labels"]), ann[(o, a)]["cotoyes"], ann[(o, a)]["wrong"])
        != (set(ann[(o, b)]["labels"]), ann[(o, b)]["cotoyes"], ann[(o, b)]["wrong"])]
    (d / "desaccords.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in disagreements),
                                        encoding="utf-8")
    result = {"n": len(kept), "mauvaise_personne": len(wrong), "mesures": m, "ic95": ci,
              "confusions": [[u, v, n] for (u, v), n in conf.most_common()]}
    (d / "accord.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(disagreements)} désaccords à arbitrer -> {d / 'desaccords.jsonl'}")
    return result

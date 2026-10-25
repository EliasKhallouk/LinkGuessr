"""Paires surprenantes (hors ligne) : deux personnes très connues, de domaines ou d'époques éloignés,
pourtant à 2 ou 3 liens l'une de l'autre. Sortie JSON avec le chemin complet et les phrases de contexte.

Mode « tendances » : repère les pics de pages vues du dernier mois et propose des paires et des
défis du jour autour de ces personnes.

  uv run python tools/surprises.py --final ../pipeline/data/work/20261001/final --top 2000 --out surprises.json
  uv run python tools/surprises.py --final ../pipeline/data/work/20261001/final --tendances --out tendances.json

Mémoire : seul le graphe « tous liens » (CSR, ~45 Mo) et quelques colonnes des fiches sont chargés ;
les phrases ne sont lues que pour les paires retenues (lecture paresseuse des parquet).
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.graph import PathResult, PersonGraph, build_csr  # noqa: E402

# Familles de domaines : changer de famille est plus surprenant que changer de domaine dans la même famille.
FAMILIES = {
    "politique": "pouvoir", "militaire": "pouvoir", "noblesse": "pouvoir", "droit": "pouvoir", "religion": "pouvoir",
    "sciences": "savoirs", "sciences humaines": "savoirs", "éducation": "savoirs", "littérature": "savoirs",
    "arts": "culture", "musique": "culture", "cinéma et télévision": "culture", "médias": "culture",
    "sport": "sport", "affaires": "affaires",
}


def domain_distance(a, b) -> float:
    if not a or not b or a == b:
        return 0.0
    return 1.0 if FAMILIES.get(a) != FAMILIES.get(b) else 0.5


def era_distance(a, b) -> float:
    if a is None or b is None:
        return 0.0
    return min(abs(a - b) / 500, 1.0)  # 0 (contemporains) à 1 (≥ 5 siècles d'écart)


class Data:
    def __init__(self, final: Path):
        self.final = final
        z = np.load(final / "graph.npz")
        self.n = len(z["qid_num"])
        self.csr = build_csr(self.n, z["a"], z["b"])
        # Nature de chaque arête (bits : 1/2 texte dans un sens, 4 relation Wikidata), pour juger la force d'un lien.
        self.edge_key = z["a"].astype(np.int64) * self.n + z["b"]
        self.edge_kinds = z["kinds"]
        # Moteur de plus courts chemins, restreint au graphe « tous liens » (le seul utile ici).
        self.engine = PersonGraph.__new__(PersonGraph)
        self.engine.n, self.engine.popularity, self.engine.csr = self.n, z["popularity"].astype(np.float32), {"all": self.csr}
        self.people = pl.read_parquet(final / "person.parquet", columns=[
            "id", "qid", "name", "description", "primary_domain", "birth_year", "popularity", "degree", "pageviews_monthly"])

    def strong(self, u: int, v: int) -> bool:
        """Lien « fort » : cité dans les deux sens, ou relation Wikidata (plutôt qu'une simple mention)."""
        a, b = min(u, v), max(u, v)
        k = int(self.edge_kinds[np.searchsorted(self.edge_key, a * self.n + b)])
        return (k & 3) == 3 or bool(k & 4)

    def row(self, i: int) -> dict:
        return self.people.row(i, named=True)  # les id sont 0..n-1, dans l'ordre

    def explain(self, path: list[int]) -> list[dict]:
        """Chaque lien du chemin avec la phrase de contexte (et la relation Wikidata s'il y en a une)."""
        pairs = list(zip(path, path[1:]))
        wanted = pl.DataFrame({"s": [a for a, b in pairs] + [b for a, b in pairs],
                               "t": [b for a, b in pairs] + [a for a, b in pairs]}, schema={"s": pl.Int32, "t": pl.Int32})
        text = (pl.scan_parquet(self.final / "text_link.parquet")
                .join(wanted.lazy(), left_on=["source_id", "target_id"], right_on=["s", "t"], how="inner")
                .select("source_id", "target_id", "snippet", "mentions").collect())
        rel = (pl.scan_parquet(self.final / "relation.parquet")
               .join(wanted.lazy(), left_on=["source_id", "target_id"], right_on=["s", "t"], how="inner")
               .select("source_id", "target_id", "label").collect())
        hops = []
        for a, b in pairs:
            t = text.filter(((pl.col("source_id") == a) & (pl.col("target_id") == b))
                            | ((pl.col("source_id") == b) & (pl.col("target_id") == a))).sort("mentions", descending=True)
            r = rel.filter(((pl.col("source_id") == a) & (pl.col("target_id") == b))
                           | ((pl.col("source_id") == b) & (pl.col("target_id") == a)))
            hops.append({
                "from": self.row(a)["name"], "to": self.row(b)["name"],
                "relation": r["label"][0] if r.height else None,
                "source_article": self.row(int(t["source_id"][0]))["name"] if t.height else None,
                "snippet": t["snippet"][0] if t.height else None,
            })
        return hops


def close_pairs(data: Data, sources: np.ndarray, targets: np.ndarray, dists: set[int]):
    """Paires (s, t) à distance 2 ou 3. Un parcours sur 2 niveaux par source, puis distance 3
    si un voisin de t a été atteint : vectorisé, sans calculer de chemin par paire."""
    csr = data.csr
    owners, neighbors = csr.expand_with_owner(targets.astype(np.int64))  # voisins de toutes les cibles
    target_pos = {int(t): i for i, t in enumerate(targets)}
    owner_pos = np.array([target_pos[int(o)] for o in owners], dtype=np.int64) if len(owners) else owners
    for s in sources.tolist():
        level1 = np.unique(csr.expand(np.array([s], dtype=np.int64)))
        level2 = np.unique(csr.expand(level1.astype(np.int64)))
        reached = np.zeros(data.n, dtype=bool)
        reached[level1] = True
        reached[level2] = True
        reached[s] = True
        within2 = np.zeros(data.n, dtype=bool)
        within2[level1] = True  # distance 1
        dist = np.full(len(targets), 0, dtype=np.int8)
        in_l2 = np.isin(targets, level2) & ~np.isin(targets, level1)
        dist[in_l2] = 2
        # distance 3 : un voisin de t est à distance ≤ 2 de s (et t n'est pas déjà à ≤ 2)
        hit = np.bincount(owner_pos[reached[neighbors]], minlength=len(targets)) > 0
        dist[(dist == 0) & hit & ~within2[targets] & (targets != s)] = 3
        for d in dists:
            for t in targets[dist == d].tolist():
                if t > s or t not in set(sources.tolist()):  # chaque paire une seule fois
                    yield s, t, d


def surprise_score(data: Data, s: int, t: int, path: list[int], n_paths: int, rank_score: dict) -> dict:
    """Score de surprise : deux personnes très connues (rang parmi les candidats), domaines et époques éloignés,
    peu de chemins possibles, intermédiaires connus et liens forts (des phrases qui ont du sens)."""
    a, b = data.row(s), data.row(t)
    popularity = math.sqrt(rank_score[s] * rank_score.get(t, 0.5))
    domain, era = domain_distance(a["primary_domain"], b["primary_domain"]), era_distance(a["birth_year"], b["birth_year"])
    rarity = 1 / (1 + math.log(max(n_paths, 1)))
    middle = path[1:-1]
    known_middle = float(np.mean(data.engine.popularity[middle])) if middle else 0.0
    strength = sum(data.strong(u, v) for u, v in zip(path, path[1:])) / (len(path) - 1)
    score = (popularity * (1 + domain) * (1 + era) * rarity * (0.5 + known_middle) * (0.5 + 0.5 * strength)
             * (1.3 if len(path) == 3 else 1.0))
    return {"score": round(score, 4), "popularity": round(popularity, 3), "domain_gap": domain, "era_gap": round(era, 2),
            "n_paths": n_paths, "strong_links": round(strength, 2), "known_middle": round(known_middle, 2)}


def person(data: Data, i: int) -> dict:
    r = data.row(i)
    return {k: r[k] for k in ("qid", "name", "description", "primary_domain", "birth_year")}


def find_surprises(data: Data, sources, targets, dists, min_gap, limit) -> list[dict]:
    candidates = []
    for s, t, d in close_pairs(data, sources, targets, dists):
        a, b = data.row(s), data.row(t)
        gap = domain_distance(a["primary_domain"], b["primary_domain"]) + era_distance(a["birth_year"], b["birth_year"])
        if gap >= min_gap:
            candidates.append((s, t, d, gap))
    # Pré-tri sur popularité × écart, puis chemins exacts (et nombre de chemins) pour les meilleurs seulement.
    pop = data.engine.popularity
    candidates.sort(key=lambda c: -(pop[c[0]] * pop[c[1]] * (1 + c[3])))
    ranked = np.argsort(-pop[targets])
    rank_score = {int(targets[i]): 1 - r / len(targets) for r, i in enumerate(ranked)}
    for s in sources.tolist():
        rank_score.setdefault(s, 1.0)
    results = []
    for s, t, d, _ in candidates[: limit * 20]:
        res: PathResult = data.engine.shortest_paths(s, t, mode="all", limit=5)
        if res.length != d:
            continue
        # Parmi les plus courts chemins, celui qui a le plus de liens forts.
        path = max(res.paths, key=lambda p: sum(data.strong(u, v) for u, v in zip(p, p[1:])))
        results.append({"from": person(data, s), "to": person(data, t), "distance": d,
                        **surprise_score(data, s, t, path, res.n_paths, rank_score), "_path": path})
    results.sort(key=lambda r: -r["score"])
    for r in results[:limit]:
        path = r.pop("_path")
        r["path"] = [data.row(i)["name"] for i in path]
        r["hops"] = data.explain(path)
    return results[:limit]


def trending(data: Data, min_views: int, min_base: int, limit: int) -> list[dict]:
    """Deux phénomènes distincts, sur le dernier mois :
    - « pic » : personne déjà lue (médiane des 11 mois précédents ≥ min_base) dont les vues s'envolent ;
    - « nouveau » : article récent (presque aucune vue avant) qui démarre fort."""
    peaks, newcomers = [], []
    for i, months in data.people.select("id", "pageviews_monthly").drop_nulls().iter_rows():
        last = months[-1]
        if last < min_views:
            continue
        base = float(np.median(months[:-1]))
        if base >= min_base:
            peaks.append((i, last, last / base, "pic"))
        else:
            newcomers.append((i, last, None, "nouveau"))
    peaks.sort(key=lambda r: -r[2])
    newcomers.sort(key=lambda r: -r[1])
    return [{"kind": kind, "person": person(data, i), "views_last_month": int(v), "spike": round(x, 1) if x else None}
            for i, v, x, kind in peaks[:limit] + newcomers[: max(1, limit // 2)]]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--final", type=Path, required=True, help="dossier des tables finales du pipeline")
    parser.add_argument("--top", type=int, default=2000, help="nombre de personnes les plus populaires considérées")
    parser.add_argument("--dist", default="2,3", help="distances retenues")
    parser.add_argument("--min-gap", type=float, default=0.8, help="écart minimal domaine + époque (0 à 2)")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--tendances", action="store_true", help="mode tendances (pics de pages vues)")
    parser.add_argument("--min-views", type=int, default=20_000, help="vues minimales le dernier mois (tendances)")
    parser.add_argument("--min-base", type=int, default=1_000, help="vues mensuelles habituelles minimales pour parler de pic")
    parser.add_argument("--out", type=Path, default=Path("surprises.json"))
    args = parser.parse_args()

    data = Data(args.final)
    pop = data.engine.popularity
    top = np.argsort(-pop)[: args.top].astype(np.int64)
    dists = {int(d) for d in args.dist.split(",")}

    if args.tendances:
        trends = trending(data, args.min_views, args.min_base, args.limit)
        for tr in trends:
            i = int(data.people.filter(pl.col("qid") == tr["person"]["qid"])["id"][0])
            tr["surprising_pairs"] = find_surprises(data, np.array([i], dtype=np.int64), top, dists, args.min_gap, 3)
            # Défi du jour possible : deux voisins connus qui ne se connaissent pas (comme app.daily.best_pair).
            neighbors = data.csr.neighbors_of(i)
            neighbors = neighbors[np.argsort(-pop[neighbors])][:25].tolist()
            sets = {v: set(data.csr.neighbors_of(v).tolist()) for v in neighbors}
            pair = next(((a, b) for k, a in enumerate(neighbors) for b in neighbors[k + 1:] if b not in sets[a]), None)
            tr["daily_candidate"] = ({"from": person(data, pair[0]), "hidden": tr["person"], "to": person(data, pair[1])}
                                     if pair else None)
        output = {"mode": "tendances", "results": trends}
    else:
        output = {"mode": "surprises", "top": args.top, "results": find_surprises(data, top, top, dists, args.min_gap, args.limit)}

    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(output['results'])} résultats -> {args.out}")


if __name__ == "__main__":
    main()

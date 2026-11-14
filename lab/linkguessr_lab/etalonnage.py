"""Étape 0 du Lab (docs/lab-plan.md, 3) : vrais volumes des données et temps d'un parcours en largeur.

Remplace les chiffres « ≈ » du plan. Écrit pipeline/data/lab/<dump>/etalonnage.json et affiche un résumé.
"""
import json
import time
from pathlib import Path

import numpy as np
import polars as pl
import psutil

ROOT = Path(__file__).resolve().parents[2]
TEXT_AB, TEXT_BA, WIKIDATA = 1, 2, 4  # bits de edge.kinds, comme backend/app/graph.py
MODES = {
    "all": lambda k: np.ones(len(k), dtype=bool),
    "strong": lambda k: ((k & (TEXT_AB | TEXT_BA)) == (TEXT_AB | TEXT_BA)) | ((k & WIKIDATA) > 0),
    "wikidata": lambda k: (k & WIKIDATA) > 0,
}
# Sections de liste : liens peu informatifs, à tester en robustesse (plan, 6.1).
LIST_SECTIONS = ["voir aussi", "filmographie", "discographie", "distinctions", "bibliographie", "œuvres",
                 "palmarès", "liens externes", "récompenses", "publications", "théâtre", "télévision"]


def rss_mb() -> float:
    return round(psutil.Process().memory_info().rss / 2**20)


def counts(df: pl.DataFrame, col: str) -> dict:
    return {str(r[col]): r["len"] for r in df.group_by(col).len().sort("len", descending=True).iter_rows(named=True)}


def volumes(final: Path) -> dict:
    out = {}
    person = pl.scan_parquet(final / "person.parquet").select(
        "gender", "primary_domain", "domains", "degree", "birth_year").collect()
    n = person.height
    out["person"] = {
        "n": n,
        "sans_domaine": round(person["primary_domain"].is_null().mean(), 4),
        "sans_annee_naissance": round(person["birth_year"].is_null().mean(), 4),
        "degre_nul": round((person["degree"] == 0).mean(), 4),
        "plusieurs_domaines": round((person["domains"].list.len() > 1).mean(), 4),
        "genre": counts(person, "gender"),
        "domaine_principal": counts(person, "primary_domain"),
    }

    edge = pl.read_parquet(final / "edge.parquet", columns=["kinds"])
    k = edge["kinds"].to_numpy()
    out["edge"] = {
        "n": len(k),
        "par_mode": {m: int(f(k).sum()) for m, f in MODES.items()},
        "texte_un_sens": int((((k & 3) == 1) | ((k & 3) == 2)).sum()),
        "texte_deux_sens": int(((k & 3) == 3).sum()),
        "wikidata_seule": int((k == WIKIDATA).sum()),
    }

    tl = pl.scan_parquet(final / "text_link.parquet")
    snip = tl.select(
        pl.len().alias("n"),
        (pl.col("snippet").is_null() | (pl.col("snippet").str.len_chars() < 20)).mean().alias("phrase_vide_ou_courte"),
        pl.col("snippet").str.len_chars().median().alias("longueur_mediane"),
        (pl.col("in_infobox") & ~pl.col("in_lead") & (pl.col("sections").list.len() == 0)).mean().alias("infobox_seule"),
        pl.col("in_lead").mean().alias("dans_intro"),
        (pl.col("mentions") > 1).mean().alias("plusieurs_mentions"),
    ).collect().row(0, named=True)
    lists = tl.select(
        pl.col("sections").list.eval(pl.element().str.to_lowercase().is_in(LIST_SECTIONS)).list.any().mean()
    ).collect().item()
    top_sections = (tl.select(pl.col("sections").list.first().str.to_lowercase().alias("s")).drop_nulls()
                    .group_by("s").len().sort("len", descending=True).head(25).collect())
    out["text_link"] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in snip.items()}
    out["text_link"]["dans_section_de_liste"] = round(lists, 4)
    out["text_link"]["premieres_sections"] = dict(top_sections.iter_rows())

    rel = pl.read_parquet(final / "relation.parquet", columns=["family", "prop", "source_id", "target_id"])
    pairs = rel.select(pl.min_horizontal("source_id", "target_id").alias("a"),
                       pl.max_horizontal("source_id", "target_id").alias("b"), "family").unique()
    out["relation"] = {
        "n": rel.height,
        "paires_distinctes": pairs.select("a", "b").unique().height,
        "par_famille": counts(rel, "family"),
        "paires_par_famille": counts(pairs, "family"),
        "proprietes": counts(rel, "prop"),
    }

    fact = pl.read_parquet(final / "fact.parquet", columns=["prop", "start_year"])
    out["fact"] = {
        "n": fact.height,
        "par_propriete": counts(fact, "prop"),
        "avec_date_debut": round(fact["start_year"].is_not_null().mean(), 4),
    }
    return out


def timed(label: str, fn, sources: np.ndarray) -> dict:
    fn(int(sources[0]))  # échauffement (caches, compilation)
    t = time.perf_counter()
    for s in sources:
        fn(int(s))
    per = (time.perf_counter() - t) / len(sources)
    print(f"  {label:10s} {per * 1000:7.0f} ms par parcours")
    return {"s_par_parcours": round(per, 4), "rss_mb": rss_mb()}


def bfs_bench(final: Path, n_sources: int) -> dict:
    z = np.load(final / "graph.npz")
    n = len(z["qid_num"])
    out = {"rss_avant_graphe_mb": rss_mb()}
    for mode, f in MODES.items():
        keep = f(z["kinds"])
        a, b = z["a"][keep], z["b"][keep]
        deg = np.bincount(np.concatenate([a, b]), minlength=n)
        out[mode] = {"arêtes": int(keep.sum()), "degre_moyen": round(2 * keep.sum() / n, 2),
                     "degre_median": int(np.median(deg)), "degre_max": int(deg.max()),
                     "personnes_isolees": int((deg == 0).sum())}

    import igraph as ig
    a, b = z["a"], z["b"]
    g = ig.Graph(n=n, edges=np.column_stack([a, b]), directed=False)
    out["rss_graphe_igraph_mb"] = rss_mb()
    for mode, f in MODES.items():
        sub = g if mode == "all" else g.subgraph_edges(np.flatnonzero(f(z["kinds"])), delete_vertices=False)
        sizes = sub.connected_components().sizes()
        out[mode]["composante_geante"] = max(sizes)
        out[mode]["part_composante_geante"] = round(max(sizes) / n, 4)
        out[mode]["composantes"] = len(sizes)
        del sub

    membership = np.array(g.connected_components().membership)
    big = np.bincount(membership).argmax()
    rng = np.random.default_rng(20261001)
    sources = rng.choice(np.flatnonzero(membership == big), size=n_sources, replace=False)

    print(f"Parcours en largeur, mode « tous les liens », {n_sources} sources :")
    bench = {"igraph": timed("igraph", lambda s: g.distances(source=s, mode="all"), sources)}

    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import shortest_path
    m = csr_matrix((np.ones(2 * len(a), dtype=np.int8), (np.concatenate([a, b]), np.concatenate([b, a]))), shape=(n, n))
    bench["scipy"] = timed("scipy", lambda s: shortest_path(m, method="D", unweighted=True, indices=s), sources)

    try:
        import networkit as nk
        gk = nk.Graph(n)
        for u, v in zip(a.tolist(), b.tolist()):
            gk.addEdge(u, v)
        bench["networkit"] = timed("networkit", lambda s: nk.distance.BFS(gk, s, storePaths=False).run(), sources)
        bench["networkit_threads"] = nk.getMaxNumberOfThreads()
    except ImportError:
        bench["networkit"] = "non installé (uv sync --extra networkit)"

    # Distances observées sur l'échantillon : premier aperçu de l'analyse 1, sans intervalle.
    hist = np.zeros(64, dtype=np.int64)
    for s in sources:
        d = np.asarray(g.distances(source=int(s))[0], dtype=float)
        d = d[np.isfinite(d) & (d > 0)].astype(int)
        hist += np.bincount(d, minlength=64)[:64]
    x = np.flatnonzero(hist)
    out["apercu_distances"] = {"histogramme": {int(i): int(hist[i]) for i in x},
                               "moyenne": round(float((x * hist[x]).sum() / hist.sum()), 3),
                               "max_observe": int(x.max())}
    out["bfs"] = bench
    out["rss_final_mb"] = rss_mb()
    return out


def run(dump: str, n_sources: int) -> None:
    final = ROOT / "pipeline" / "data" / "work" / dump / "final"
    t0 = time.perf_counter()
    result = {"dump": dump, "cpu_logiques": psutil.cpu_count(), "ram_go": round(psutil.virtual_memory().total / 2**30, 1)}
    print("Volumes…")
    result["volumes"] = volumes(final)
    result["graphe"] = bfs_bench(final, n_sources)
    result["duree_s"] = round(time.perf_counter() - t0)

    out = ROOT / "pipeline" / "data" / "lab" / dump / "etalonnage.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Écrit : {out} ({result['duree_s']} s, mémoire max vue {result['graphe']['rss_final_mb']} Mo)")

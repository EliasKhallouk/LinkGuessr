"""Graphe final : identifiants numériques, arêtes pondérées et métriques par personne.

Sorties (dossier work/final) : person, ref, fact, text_link, relation, edge (.parquet),
prêtes à être chargées telles quelles dans Postgres par `lg load`, et graph.npz pour l'API.
"""
import unicodedata

import igraph as ig
import numpy as np
import polars as pl

from .config import DUMP_DATE, work_path


def normalize(s: str) -> str:
    """Minuscules sans accents (même règle que l'API pour la recherche)."""
    s = unicodedata.normalize("NFKD", s.replace("œ", "oe").replace("æ", "ae").replace("Œ", "Oe").replace("Æ", "Ae"))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _search_text(row: dict) -> str:
    parts = [row["name"], (row["title"] or "").replace("_", " "), row["birth_name"],
             *(row["aliases"] or []), *(row["pseudonyms"] or [])]
    parts = [p for p in parts if p]
    seen, out = set(), []
    for p in parts:
        n = normalize(p).strip()
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return " | ".join(out)


def _pct_rank(col: str) -> pl.Expr:
    return (pl.col(col).fill_null(0).rank("average") / pl.len()).cast(pl.Float32)


def build_graph() -> None:
    final = work_path("final")
    final.mkdir(exist_ok=True)

    # Le titre du dump fait foi (la fiche Wikidata a pu perdre son lien frwiki depuis) ;
    # sans libellé Wikidata, le nom vient du titre (sans la précision entre parenthèses).
    dump_titles = pl.read_parquet(work_path("humans.parquet"), columns=["qid", "title"]).rename({"title": "dump_title"})
    persons = (
        pl.read_parquet(work_path("persons.parquet"))
        .join(dump_titles, on="qid", how="left")
        .with_columns(pl.coalesce("dump_title", "title").alias("title")).drop("dump_title")
        .with_columns(pl.coalesce("name", pl.col("title").str.replace_all("_", " ").str.replace(r"\s*\(.*\)$", ""))
                      .alias("name"))
        .with_columns(pl.col("qid").str.slice(1).cast(pl.Int64).alias("_n"))
        .sort("_n").drop("_n")
        .with_row_index("id")
        .with_columns(pl.col("id").cast(pl.Int32))
    )
    ids = persons.select("qid", "id")
    n = persons.height

    # Tables lues en mode « paresseux » : seules les colonnes utiles au calcul sont chargées en mémoire,
    # les grosses tables (phrases, faits) sont transformées en flux directement vers les fichiers finaux.
    def with_ids(frame: pl.LazyFrame, *cols: str) -> pl.LazyFrame:
        for c in cols:
            frame = frame.join(ids.lazy().rename({"qid": c, "id": c.replace("_qid", "_id")}), on=c, how="inner").drop(c)
        return frame

    text_links = with_ids(pl.scan_parquet(work_path("text_links.parquet")).select("source_qid", "target_qid", "mentions"),
                          "source_qid", "target_qid").collect()
    relations = with_ids(pl.scan_parquet(work_path("relations.parquet")), "source_qid", "target_qid").collect()

    # Arêtes non orientées (a < b) : fusion des liens textuels (deux sens) et des relations Wikidata.
    text_edges = text_links.select(
        pl.min_horizontal("source_id", "target_id").alias("a"),
        pl.max_horizontal("source_id", "target_id").alias("b"),
        pl.when(pl.col("source_id") < pl.col("target_id")).then(1).otherwise(2).alias("kinds"),
        pl.col("mentions").cast(pl.Int32),
    )
    rel_edges = relations.select(
        pl.min_horizontal("source_id", "target_id").alias("a"),
        pl.max_horizontal("source_id", "target_id").alias("b"),
    ).unique().with_columns(pl.lit(4).alias("kinds"), pl.lit(0, pl.Int32).alias("mentions"))
    edges = (
        pl.concat([text_edges, rel_edges])
        .group_by("a", "b")
        .agg(pl.col("kinds").sum(), pl.col("mentions").sum())
        .with_columns(
            # Force : mentions (log) + bonus si le lien est réciproque + bonus si relation Wikidata.
            (pl.col("mentions").log1p()
             + ((pl.col("kinds") & 3) == 3).cast(pl.Float32)
             + 2 * ((pl.col("kinds") & 4) > 0).cast(pl.Float32)).cast(pl.Float32).alias("weight"),
            pl.col("kinds").cast(pl.Int16),
            pl.col("mentions").clip(upper_bound=32767).cast(pl.Int16),
        )
        .sort("a", "b")
    )

    # Métriques (igraph, en C).
    g_dir = ig.Graph(n=n, edges=text_links.select("source_id", "target_id").to_numpy(), directed=True)
    g_und = ig.Graph(n=n, edges=edges.select("a", "b").to_numpy(), directed=False)
    g_und.es["weight"] = edges["weight"].to_list()
    communities = g_und.community_leiden(objective_function="modularity", weights="weight", n_iterations=4)
    print(f"{n:,} personnes, {edges.height:,} arêtes, {len(communities):,} communautés "
          f"(modularité {communities.modularity:.3f})")

    persons = persons.with_columns(
        pl.Series("degree", g_und.degree(), pl.Int32),
        pl.Series("in_links", g_dir.indegree(), pl.Int32),
        pl.Series("out_links", g_dir.outdegree(), pl.Int32),
        pl.Series("pagerank", g_dir.pagerank(directed=True), pl.Float32),
        pl.Series("community", communities.membership, pl.Int32),
    )
    # Popularité : moyenne pondérée de rangs percentiles (les signaux ont des échelles et des
    # queues de distribution très différentes, les rangs les rendent comparables).
    #  - pages vues 12 mois : notoriété actuelle auprès des lecteurs français (le plus proche des joueurs)
    #  - sitelinks : notoriété internationale et durable
    #  - PageRank : importance dans le réseau frwiki
    #  - longueur de l'article : intérêt de la communauté (bruité, poids faible)
    if "pageviews_12m" not in persons.columns:
        persons = persons.with_columns(pl.lit(None, pl.Int64).alias("pageviews_12m"))
    persons = persons.with_columns(
        (0.4 * _pct_rank("pageviews_12m") + 0.3 * _pct_rank("sitelinks")
         + 0.2 * _pct_rank("pagerank") + 0.1 * _pct_rank("article_len"))
        .alias("popularity"),
        pl.Series("search_text", [_search_text(r) for r in persons.iter_rows(named=True)], pl.Utf8),
    )

    persons.write_parquet(final / "person.parquet")
    pl.read_parquet(work_path("refs.parquet")).write_parquet(final / "ref.parquet")
    with_ids(pl.scan_parquet(work_path("facts.parquet")), "person_qid").sink_parquet(final / "fact.parquet")
    with_ids(pl.scan_parquet(work_path("text_links.parquet")), "source_qid", "target_qid").sink_parquet(
        final / "text_link.parquet")
    relations.write_parquet(final / "relation.parquet")
    edges.write_parquet(final / "edge.parquet")

    # Graphe binaire chargé par l'API au démarrage (bien plus rapide que de relire la table edge).
    domains = sorted(d for d in persons["primary_domain"].unique().to_list() if d)
    domain_code = {d: i for i, d in enumerate(domains)}
    np.savez_compressed(
        final / "graph.npz",
        qid_num=persons["qid"].str.slice(1).cast(pl.Int64).to_numpy(),  # croissant : id = position
        a=edges["a"].to_numpy(), b=edges["b"].to_numpy(), kinds=edges["kinds"].to_numpy(),
        popularity=persons["popularity"].to_numpy(),
        domain=np.array([domain_code.get(d, -1) for d in persons["primary_domain"].to_list()], dtype=np.int8),
        domain_names=np.array(domains),
        birth_year=persons["birth_year"].fill_null(-99999).to_numpy().astype(np.int32),
        dump_date=np.array(DUMP_DATE),
    )
    print(f"tables finales dans {final}")

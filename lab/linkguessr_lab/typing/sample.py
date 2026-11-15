"""Tirage stratifié des phrases du jeu d'or (lab/annotation/guide.md, docs/lab-plan.md 0.1).

Un tirage uniforme serait écrasé par les filmographies et les palmarès : les classes rares (couple, critique…)
n'auraient presque pas d'exemples. On tire donc par strates disjointes, et chaque phrase garde sa strate et son
poids (taille de la strate / effectif tiré) pour que les proportions estimées sur le jeu d'or puissent être
ramenées à l'ensemble des phrases.

Strates :
  nom/<variant>          mentions sans lien (complet, libelle, famille)
  infobox, legende
  lien/wd/<famille>      phrases d'une paire qui porte une relation Wikidata, par famille de relation
  lien/autre/<domaine>   les autres phrases, par domaine principal de A (allocation en racine carrée)

Garde-fous : une phrase par paire, trois phrases au plus par article, phrases de 30 à 500 caractères.
Les 300 phrases de l'accord inter-annotateurs sont tirées au hasard parmi les 1 500 (même répartition).
"""
import json
from pathlib import Path

import numpy as np
import polars as pl

ROOT = Path(__file__).resolve().parents[3]
SEED = 20261115
N_TOTAL = 1500
N_ACCORD = 300
ALLOC = {"nom": 300, "infobox": 120, "legende": 80, "lien/wd": 300, "lien/autre": 700}
MAX_PER_SOURCE = 3


def sqrt_alloc(sizes: dict[str, int], n: int) -> dict[str, int]:
    """Répartit n entre strates proportionnellement à la racine de leur taille (au moins 1 chacune)."""
    w = {k: np.sqrt(v) for k, v in sizes.items() if v > 0}
    total = sum(w.values())
    out = {k: max(1, round(n * v / total)) for k, v in w.items()}
    while sum(out.values()) != n:  # arrondis : on corrige sur la plus grosse strate
        out[max(out, key=out.get)] += 1 if sum(out.values()) < n else -1
    return out


def run(dump: str = "20261001") -> Path:
    work = ROOT / "pipeline" / "data" / "work" / dump
    final = work / "final"
    person = pl.read_parquet(final / "person.parquet",
                             columns=["id", "qid", "name", "birth_year", "death_year", "primary_domain"])
    qid_of = person.select("id", "qid")
    rel = (pl.read_parquet(final / "relation.parquet", columns=["family", "source_id", "target_id"])
           .join(qid_of.rename({"id": "source_id", "qid": "a"}), on="source_id")
           .join(qid_of.rename({"id": "target_id", "qid": "b"}), on="target_id"))
    # Relation non orientée : une paire (A, B) porte la famille si A→B ou B→A existe.
    rel = pl.concat([rel.select("a", "b", "family"), rel.select(pl.col("b").alias("a"), pl.col("a").alias("b"), "family")])
    rel = rel.group_by("a", "b").agg(pl.col("family").first())

    s = (pl.scan_parquet(work / "link_sentences.parquet")
         .with_row_index("row")
         .filter(pl.col("sentence").str.len_chars().is_between(30, 500))
         .select("row", "source_qid", "target_qid", "kind", "variant")
         .collect())
    s = (s.join(rel, left_on=["source_qid", "target_qid"], right_on=["a", "b"], how="left")
          .join(person.select(pl.col("qid").alias("source_qid"), pl.col("primary_domain").fill_null("sans domaine")),
                on="source_qid", how="left"))
    s = s.with_columns(
        pl.when(pl.col("kind") == "nom").then(pl.concat_str(pl.lit("nom/"), "variant"))
        .when(pl.col("kind").is_in(["infobox", "legende"])).then(pl.col("kind"))
        .when(pl.col("family").is_not_null()).then(pl.concat_str(pl.lit("lien/wd/"), "family"))
        .otherwise(pl.concat_str(pl.lit("lien/autre/"), "primary_domain")).alias("strate"))
    sizes = dict(s.group_by("strate").len().iter_rows())

    plan: dict[str, int] = {}
    for group, n in ALLOC.items():
        members = {k: v for k, v in sizes.items() if k == group or k.startswith(group + "/")}
        plan |= sqrt_alloc(members, n) if len(members) > 1 else {group: n}

    rng = np.random.default_rng(SEED)
    s = s.with_columns(pl.Series("u", rng.random(s.height)))
    picked, per_source, pairs = [], {}, set()
    # On parcourt chaque strate dans un ordre aléatoire en appliquant les garde-fous.
    for strate, n in sorted(plan.items()):
        cand = s.filter(pl.col("strate") == strate).sort("u").head(n * 50)
        got = 0
        for r in cand.iter_rows(named=True):
            pair = (r["source_qid"], r["target_qid"])
            if pair in pairs or per_source.get(r["source_qid"], 0) >= MAX_PER_SOURCE:
                continue
            pairs.add(pair)
            per_source[r["source_qid"]] = per_source.get(r["source_qid"], 0) + 1
            picked.append({"row": r["row"], "strate": strate, "poids": sizes[strate] / n})
            got += 1
            if got == n:
                break
    sample = pl.DataFrame(picked)

    full = (pl.scan_parquet(work / "link_sentences.parquet").with_row_index("row")
            .filter(pl.col("row").is_in(sample["row"].implode())).collect()
            .join(sample, on="row"))
    years = person.select("qid", "name", "birth_year", "death_year")
    full = (full.join(years.rename(lambda c: f"a_{c}" if c != "qid" else "source_qid"), on="source_qid")
                .join(years.rename(lambda c: f"b_{c}" if c != "qid" else "target_qid"), on="target_qid"))
    # Vies qui se chevauchent : « non » d'office à « se sont-ils côtoyés ? » quand elles ne se chevauchent pas.
    end_a = pl.col("a_death_year").fill_null(2026)
    end_b = pl.col("b_death_year").fill_null(2026)
    full = full.with_columns(
        pl.when(pl.col("a_birth_year").is_null() | pl.col("b_birth_year").is_null()).then(None)
        .otherwise(pl.max_horizontal("a_birth_year", "b_birth_year") <= pl.min_horizontal(end_a, end_b))
        .alias("vies_chevauchent"))

    full = full.with_columns(pl.Series("u", np.random.default_rng(SEED + 1).random(full.height))).sort("u")
    full = full.with_row_index("ordre").with_columns((pl.col("ordre") < N_ACCORD).alias("accord")).drop("u", "row")

    out_dir = ROOT / "pipeline" / "data" / "lab" / dump / "annotation"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "items.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for r in full.iter_rows(named=True):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    counts = full.group_by("strate").len().sort("strate")
    print(f"{full.height} phrases ({full['accord'].sum()} pour l'accord) dans {counts.height} strates : {out}")
    return out

"""Articles de frwiki (espace principal), leur QID Wikidata et les redirections.

Sorties :
  articles.parquet  page_id, title, is_redirect, length, qid
  redirects.parquet from_title, to_title
Les titres gardent le format des dumps (underscores à la place des espaces).
"""
import polars as pl
from tqdm import tqdm

from .config import dump_path, work_path
from .sqldump import read_table


def build_pages() -> None:
    ids, titles, redirects, lengths = [], [], [], []
    rows = read_table(dump_path("page.sql.gz"), "page",
                      ["page_id", "page_namespace", "page_title", "page_is_redirect", "page_len"])
    for page_id, ns, title, is_redirect, length in tqdm(rows, desc="page", unit=" lignes", unit_scale=True):
        if ns == 0:
            ids.append(page_id)
            titles.append(title)
            redirects.append(bool(is_redirect))
            lengths.append(length)
    pages = pl.DataFrame({"page_id": ids, "title": titles, "is_redirect": redirects, "length": lengths},
                         schema={"page_id": pl.Int64, "title": pl.Utf8, "is_redirect": pl.Boolean, "length": pl.Int64})

    props = [(page, value) for page, name, value in tqdm(
        read_table(dump_path("page_props.sql.gz"), "page_props", ["pp_page", "pp_propname", "pp_value"]),
        desc="page_props", unit=" lignes", unit_scale=True,
    ) if name == "wikibase_item"]
    qids = pl.DataFrame(props, schema={"page_id": pl.Int64, "qid": pl.Utf8}, orient="row")

    articles = pages.join(qids, on="page_id", how="left")
    articles.write_parquet(work_path("articles.parquet"))

    rd = [(src, target) for src, ns, target, interwiki in tqdm(
        read_table(dump_path("redirect.sql.gz"), "redirect", ["rd_from", "rd_namespace", "rd_title", "rd_interwiki"]),
        desc="redirect", unit=" lignes", unit_scale=True,
    ) if ns == 0 and not interwiki]
    rd_df = pl.DataFrame(rd, schema={"page_id": pl.Int64, "to_title": pl.Utf8}, orient="row")
    redirects_df = (
        rd_df.join(pages.select("page_id", "title"), on="page_id", how="inner")
        .select(pl.col("title").alias("from_title"), "to_title")
    )
    redirects_df.write_parquet(work_path("redirects.parquet"))

    n_articles = articles.filter(~pl.col("is_redirect")).height
    n_qid = articles.filter(~pl.col("is_redirect") & pl.col("qid").is_not_null()).height
    print(f"{n_articles:,} articles ({n_qid:,} avec QID), {redirects_df.height:,} redirections")

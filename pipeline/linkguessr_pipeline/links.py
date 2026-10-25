"""Extrait les liens entre personnes depuis le wikitexte des biographies.

Le dump « multistream » est découpé en blocs bz2 indépendants de 100 pages,
localisés par un index : on décompresse en parallèle uniquement les blocs
qui contiennent au moins une biographie.

Pour chaque biographie, on parcourt le wikitexte en suivant le contexte :
section courante, profondeur de modèles ({{...}}), notes <ref> (ignorées :
ce sont des sources, pas des relations), commentaires et balises spéciales.
Les modèles de navigation (palettes) n'apparaissent pas dans le wikitexte,
donc leurs liens sont naturellement exclus.

Sorties :
  text_links.parquet  source_qid, target_qid, mentions, first_pos (0-1),
                      in_lead, in_infobox, sections (liste), snippet
  pages_text.parquet  qid, infobox, categories, lead, n_chars, n_sections
"""
import bz2
import html
import os
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import polars as pl
from tqdm import tqdm

from .config import dump_path, work_path

_TOKEN = re.compile(
    r"(?P<comment><!--.*?(?:-->|\Z))"
    r"|(?P<skip><(?P<skiptag>gallery|math|nowiki|syntaxhighlight|source|code|pre|timeline|score)\b[^>]*>.*?</(?P=skiptag)\s*>)"
    r"|(?P<refself><ref\b[^>]*/>)"
    r"|(?P<refopen><ref\b[^>]*>)"
    r"|(?P<refclose></ref\s*>)"
    r"|(?P<heading>^(?P<hlevel>={2,6})[ \t]*(?P<htitle>.+?)[ \t]*(?P=hlevel)[ \t]*$)"
    r"|(?P<tplopen>\{\{\s*(?P<tplname>[^|{}\n]*))"
    r"|(?P<tplclose>\}\})"
    r"|(?P<fileopen>\[\[\s*(?:Fichier|File|Image)\s*:)"
    r"|(?P<link>\[\[(?P<target>[^\[\]|\n]+)(?:\|(?P<label>[^\[\]]*))?\]\])"
    r"|(?P<close>\]\])",  # fermeture d'un [[Fichier:...]] (les liens simples consomment leur propre ]])
    re.DOTALL | re.MULTILINE,
)
_CATEGORY = re.compile(r"\[\[\s*(?:Catégorie|Category)\s*:\s*([^\]|]+)", re.IGNORECASE)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s|\n")


def normalize_title(raw: str) -> str | None:
    """Convertit une cible de lien wikitexte vers le format des titres du dump."""
    t = html.unescape(raw).split("#", 1)[0].replace("_", " ").strip()
    t = t.lstrip(":").strip()
    if not t:
        return None
    t = re.sub(r"\s+", " ", t)
    return (t[0].upper() + t[1:]).replace(" ", "_")


def _positional(parts: list[str]) -> list[str]:
    return [p.strip() for p in parts if "=" not in p]


def _inline_template(m: re.Match) -> str:
    """Rend en texte les modèles « en ligne » courants de frwiki, supprime les autres."""
    parts = m.group(1).split("|")
    name, args = parts[0].strip().lower(), _positional(parts[1:])
    named = dict(p.split("=", 1) for p in parts[1:] if "=" in p)
    if name.startswith("date"):
        return " ".join(args[:3])
    if name in ("lang", "langue", "japonais", "chinois", "coréen", "arabe", "hébreu", "russe"):
        return args[-1] if args else ""
    if name in ("nobr", "nowrap", "souverain", "souverain2", "souverain3", "nom", "unité", "pc", "sc", "petites capitales"):
        return " ".join(args)
    if name in ("guil", "citation", "«"):
        return f"« {' '.join(args)} »"
    if name in ("siècle", "s", "s-", "-s", "-s-"):
        return f"{args[0]}e siècle" if args else ""
    if name in ("e", "er", "re", "1er", "1re", "ers", "res", "es", "nd", "nde"):
        return name.lstrip("1") if name.startswith("1") else name
    if name in ("nombre", "formatnum", "formatnum:"):
        return " ".join(args[:2])
    if name == "lien":
        return named.get("fr", args[0] if args else "").strip()
    return ""


def clean_wikitext(s: str) -> str:
    """Nettoyage du wikitexte en texte lisible (pour extraits et introductions)."""
    s = re.sub(r"<!--.*?-->", "", s, flags=re.DOTALL)
    s = re.sub(r"<ref\b[^>]*/>|<ref\b[^>]*>.*?</ref\s*>", "", s, flags=re.DOTALL)
    for _ in range(5):  # modèles imbriqués : on traite de l'intérieur vers l'extérieur
        s, n = re.subn(r"\{\{([^{}]*)\}\}", _inline_template, s)
        if not n:
            break
    for _ in range(3):  # liens, puis images dont la légende contenait des liens
        s = re.sub(r"\[\[(?:Fichier|File|Image)\s*:[^\[\]]*\]\]", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\[\[[^\[\]|]*\|([^\[\]]*)\]\]", r"\1", s)
        s = re.sub(r"\[\[([^\[\]]*)\]\]", r"\1", s)
    s = re.sub(r"\[https?://\S+\s([^\]]*)\]", r"\1", s)
    s = re.sub(r"'{2,}", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"\(\s*[,;]?\s*\)", "", s)  # parenthèses vidées (prononciation, dates manquantes)
    s = re.sub(r"\s+([,.])", r"\1", s)
    return re.sub(r"\s+", " ", s).strip()


def _snippet(text: str, start: int, end: int) -> str:
    """Phrase qui contient le lien (bornée à environ 300 caractères de chaque côté)."""
    lo = max(0, start - 300)
    before = list(_SENTENCE_END.finditer(text, lo, start))
    s = before[-1].end() if before else lo
    after = _SENTENCE_END.search(text, end, min(len(text), end + 300))
    e = after.start() + 1 if after else min(len(text), end + 300)
    out = clean_wikitext(text[s:e])
    # Fenêtre coupée au milieu d'un modèle ou d'une note : on retire le morceau orphelin.
    out = re.split(r"\{\{|<ref|\[\[", out)[0]
    out = re.split(r"\}\}|</ref>|\]\]", out)[-1]
    return out.strip()[:500]


def _lead(text: str) -> str:
    """Premier paragraphe de texte de l'introduction (avant la première section)."""
    intro = re.split(r"^==", text, maxsplit=1, flags=re.MULTILINE)[0]
    for para in re.split(r"\n\s*\n", intro):
        cleaned = clean_wikitext(para)
        if len(cleaned) > 80 and not cleaned.startswith(("|", "{", "!")):
            return cleaned[:1500]
    return ""


def analyze_page(text: str, title_to_qid: dict[str, str], self_qid: str) -> tuple[dict, dict]:
    links: dict[str, dict] = {}
    section = "intro"
    sections_seen = 0
    tpl_stack: list[str] = []
    ref_depth = 0
    file_depth = 0
    infobox = None
    n = max(len(text), 1)

    for m in _TOKEN.finditer(text):
        if m.group("comment") or m.group("skip") or m.group("refself"):
            continue
        if m.group("refopen"):
            ref_depth += 1
        elif m.group("refclose"):
            ref_depth = max(0, ref_depth - 1)
        elif m.group("heading"):
            if not tpl_stack and not ref_depth:
                section = clean_wikitext(m.group("htitle"))[:80] or "?"
                sections_seen += 1
        elif m.group("tplopen"):
            name = m.group("tplname").strip()
            tpl_stack.append(name)
            if infobox is None and name.lower().startswith("infobox"):
                infobox = name
        elif m.group("tplclose"):
            if tpl_stack:
                tpl_stack.pop()
        elif m.group("fileopen"):
            file_depth += 1
        elif m.group("close"):
            file_depth = max(0, file_depth - 1)
        elif m.group("link") and not ref_depth:
            target = normalize_title(m.group("target"))
            qid = title_to_qid.get(target) if target else None
            if not qid or qid == self_qid:
                continue
            in_infobox = bool(tpl_stack) and tpl_stack[0].lower().startswith("infobox")
            if tpl_stack and not in_infobox:
                continue  # liens dans d'autres modèles (références, {{Lien}}...) : pas des relations
            entry = links.get(qid)
            if entry is None:
                entry = links[qid] = {
                    "mentions": 0, "first_pos": m.start() / n, "in_lead": False, "in_infobox": False,
                    "sections": [], "snippet": None, "caption": None,
                }
            entry["mentions"] += 1
            if in_infobox:
                entry["in_infobox"] = True
            elif file_depth:
                if entry["caption"] is None:  # légende d'image : extrait de secours seulement
                    entry["caption"] = clean_wikitext(m.group("label") or m.group("target"))
            else:
                if section == "intro":
                    entry["in_lead"] = True
                if section not in entry["sections"]:
                    entry["sections"].append(section)
                if entry["snippet"] is None:
                    entry["snippet"] = _snippet(text, m.start(), m.end())

    for entry in links.values():
        caption = entry.pop("caption")
        if entry["snippet"] is None:
            entry["snippet"] = caption

    page = {
        "infobox": infobox,
        "categories": sorted({c.strip() for c in _CATEGORY.findall(text)}),
        "lead": _lead(text),
        "n_chars": len(text),
        "n_sections": sections_seen,
    }
    return links, page


# --- Traitement parallèle des blocs du dump -----------------------------------------------

_W: dict = {}


def _init_worker(dump: str, title_to_qid: dict[str, str], page_to_qid: dict[int, str]) -> None:
    _W["dump"] = dump
    _W["title_to_qid"] = title_to_qid
    _W["page_to_qid"] = page_to_qid


def _process_block(span: tuple[int, int]) -> tuple[list[dict], list[dict]]:
    start, end = span
    with open(_W["dump"], "rb") as f:
        f.seek(start)
        raw = f.read(end - start) if end > 0 else f.read()
    xml = bz2.BZ2Decompressor().decompress(raw).decode("utf-8")
    root = ET.fromstring(f"<root>{xml}</root>")

    link_rows, page_rows = [], []
    for page in root.iter("page"):
        if page.findtext("ns") != "0" or page.find("redirect") is not None:
            continue
        qid = _W["page_to_qid"].get(int(page.findtext("id")))
        if not qid:
            continue
        text = page.findtext("revision/text") or ""
        links, info = analyze_page(text, _W["title_to_qid"], qid)
        page_rows.append({"qid": qid, **info})
        for target, e in links.items():
            link_rows.append({"source_qid": qid, "target_qid": target, **e})
    return link_rows, page_rows


def extract_links(workers: int | None = None) -> None:
    humans = pl.read_parquet(work_path("humans.parquet"))
    page_to_qid = dict(zip(humans["page_id"].to_list(), humans["qid"].to_list()))
    title_to_qid = dict(zip(humans["title"].to_list(), humans["qid"].to_list()))
    # Les liens vers une redirection (ex. « Zizou ») comptent pour la personne visée.
    redirects = pl.read_parquet(work_path("redirects.parquet")).join(
        humans.select(pl.col("title").alias("to_title"), "qid"), on="to_title", how="inner")
    for src, qid in zip(redirects["from_title"].to_list(), redirects["qid"].to_list()):
        title_to_qid.setdefault(src, qid)

    # Index multistream : « offset:page_id:titre ». Un bloc s'étend jusqu'à l'offset suivant.
    offsets_with_humans: set[int] = set()
    all_offsets: set[int] = set()
    with bz2.open(dump_path("pages-articles-multistream-index.txt.bz2"), "rt", encoding="utf-8") as f:
        for line in f:
            offset, page_id, _ = line.split(":", 2)
            offset = int(offset)
            all_offsets.add(offset)
            if int(page_id) in page_to_qid:
                offsets_with_humans.add(offset)
    ordered = sorted(all_offsets)
    next_offset = dict(zip(ordered, ordered[1:] + [-1]))
    spans = [(o, next_offset[o]) for o in sorted(offsets_with_humans)]
    print(f"{len(spans):,} blocs à lire sur {len(ordered):,}, {len(title_to_qid):,} titres reconnus")

    dump = str(dump_path("pages-articles-multistream.xml.bz2"))
    all_links, all_pages = [], []
    with ProcessPoolExecutor(workers or os.cpu_count(), initializer=_init_worker,
                             initargs=(dump, title_to_qid, page_to_qid)) as pool:
        for link_rows, page_rows in tqdm(pool.map(_process_block, spans, chunksize=64),
                                         total=len(spans), desc="blocs", unit="bloc"):
            all_links.extend(link_rows)
            all_pages.extend(page_rows)

    links_df = pl.DataFrame(all_links, schema={
        "source_qid": pl.Utf8, "target_qid": pl.Utf8, "mentions": pl.Int32, "first_pos": pl.Float32,
        "in_lead": pl.Boolean, "in_infobox": pl.Boolean, "sections": pl.List(pl.Utf8), "snippet": pl.Utf8,
    })
    links_df.write_parquet(work_path("text_links.parquet"), compression="zstd")
    pages_df = pl.DataFrame(all_pages, schema={
        "qid": pl.Utf8, "infobox": pl.Utf8, "categories": pl.List(pl.Utf8), "lead": pl.Utf8,
        "n_chars": pl.Int32, "n_sections": pl.Int16,
    })
    pages_df.write_parquet(work_path("pages_text.parquet"), compression="zstd")
    print(f"{links_df.height:,} liens entre {pages_df.height:,} biographies")

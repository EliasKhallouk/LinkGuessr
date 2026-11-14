"""Toutes les phrases où une biographie parle d'une autre personne (Lab : typage des liens).

`lg links` ne garde qu'une phrase par paire, celle du premier lien. Ici, une ligne par occurrence :
  lien      chaque lien [[...]] vers la personne dans le corps du texte
  infobox   lien dans l'infobox, rendu « paramètre : valeur » (ex. « conjoint : Pierre Curie »)
  legende   lien dans une légende d'image
  nom       mention sans lien, après le premier lien : nom complet, texte d'un lien, ou nom de famille
Les pronoms (« il », « elle ») ne sont pas résolus.

Le parcours du wikitexte est celui de links.analyze_page (mêmes exclusions : notes, modèles autres que
l'infobox). Une mention sans lien n'est cherchée que dans le texte courant (hors liens, modèles, notes,
titres et légendes), et seulement si le nom désigne une seule personne liée de la page, et pas le
sujet de l'article (« Curie » dans l'article de Marie Curie).

Sortie, hors tables finales (ni Postgres ni site) :
  link_sentences.parquet  source_qid, target_qid, kind, variant, section, position (0-1), sentence
"""
import os
import re
import shutil
from bisect import bisect_right
from concurrent.futures import ProcessPoolExecutor

import polars as pl
from tqdm import tqdm

from .config import dump_path, work_path
from .links import _TOKEN, _snippet, block_pages, clean_wikitext, human_blocks, human_titles, normalize_title

MAX_PER_PAIR = 30  # au-delà, les phrases d'une même paire se répètent (Napoléon cité 200 fois)
PARTICLES = {"de", "du", "des", "d'", "von", "van", "der", "di", "da", "del", "le", "la", "ibn", "ben"}
_REGNAL = re.compile(r"^(?:[IVXLC]+|Ier|Ire|Iere)$")
_INFOBOX_PARAM = re.compile(r"^\s*\|\s*([^=|{}\[\]]+?)\s*=")
_FILE_PARTS = re.compile(r"\[\[|\]\]|\{\{|\}\}|\|")
_WORD_BEFORE = re.compile(r"([\w'’-]+)\s*$")

FLUSH_ROWS = 1_000_000
SCHEMA = {
    "source_qid": pl.Utf8, "target_qid": pl.Utf8, "kind": pl.Utf8, "variant": pl.Utf8,
    "section": pl.Utf8, "position": pl.Float32, "sentence": pl.Utf8,
}


def _display_name(title: str) -> str:
    return re.sub(r"\s*\([^)]*\)$", "", title.replace("_", " ")).strip()


def _surname(name: str) -> str | None:
    words = name.split()
    if len(words) < 2 or _REGNAL.match(words[-1]):
        return None
    last = words[-1]
    if words[-2].lower() in PARTICLES:  # « de Gaulle », pas « Gaulle »
        last = f"{words[-2]} {last}"
    return last if len(last) >= 4 and last[-1].isalpha() and words[-1][0].isupper() else None


def _infobox_line(text: str, start: int, label: str) -> str:
    line = text[text.rfind("\n", 0, start) + 1:start]
    m = _INFOBOX_PARAM.match(line)
    return f"{m.group(1).strip()} : {label}" if m else label


def _caption(text: str, file_start: int, start: int) -> str:
    """Paramètre de [[Fichier:…|…]] qui contient le lien : la légende, liens internes compris."""
    depth, tpl, s = 0, 0, file_start
    for m in _FILE_PARTS.finditer(text, file_start, file_start + 5000):
        tok = m.group()
        if tok == "[[":
            depth += 1
        elif tok == "]]":
            depth -= 1
            if depth == 0:
                return clean_wikitext(text[s:m.start()])
        elif tok == "{{":
            tpl += 1
        elif tok == "}}":
            tpl = max(0, tpl - 1)
        elif depth == 1 and not tpl:  # « | » au premier niveau : début d'un nouveau paramètre
            if m.start() > start:
                return clean_wikitext(text[s:m.start()])
            s = m.end()
    return ""


def page_sentences(text: str, title_to_qid: dict[str, str], self_qid: str, self_name: str,
                   qid_to_name: dict[str, str], places: frozenset[str] = frozenset()) -> list[dict]:
    rows: list[dict] = []
    section = "intro"
    tpl_stack: list[str] = []
    ref_depth = 0
    file_starts: list[int] = []
    body: list[tuple[int, int]] = []  # zones de texte courant, entre les éléments de wikitexte
    zone_start = 0
    first: dict[str, int] = {}
    labels: dict[str, set[str]] = {}
    n = max(len(text), 1)
    sections_at: list[tuple[int, str]] = [(0, section)]

    def add(qid: str, kind: str, variant: str, pos: int, sentence: str) -> None:
        if sentence:
            rows.append({"source_qid": self_qid, "target_qid": qid, "kind": kind, "variant": variant,
                         "section": section, "position": pos / n, "sentence": sentence})

    for m in _TOKEN.finditer(text):
        clean = not tpl_stack and not ref_depth and not file_starts
        if clean and m.start() > zone_start:
            body.append((zone_start, m.start()))
        if m.group("comment") or m.group("skip") or m.group("refself"):
            pass
        elif m.group("refopen"):
            ref_depth += 1
        elif m.group("refclose"):
            ref_depth = max(0, ref_depth - 1)
        elif m.group("heading"):
            if not tpl_stack and not ref_depth:
                section = clean_wikitext(m.group("htitle"))[:80] or "?"
                sections_at.append((m.start(), section))
        elif m.group("tplopen"):
            tpl_stack.append(m.group("tplname").strip())
        elif m.group("tplclose"):
            if tpl_stack:
                tpl_stack.pop()
        elif m.group("fileopen"):
            file_starts.append(m.start())
        elif m.group("close"):
            if file_starts:
                file_starts.pop()
        elif m.group("link") and not ref_depth:
            target = normalize_title(m.group("target"))
            qid = title_to_qid.get(target) if target else None
            in_infobox = bool(tpl_stack) and tpl_stack[0].lower().startswith("infobox")
            if qid and qid != self_qid and not (tpl_stack and not in_infobox):
                label = clean_wikitext(m.group("label") or m.group("target"))
                if in_infobox:
                    add(qid, "infobox", "lien", m.start(), _infobox_line(text, m.start(), label))
                elif file_starts:
                    add(qid, "legende", "lien", m.start(), _caption(text, file_starts[-1], m.start()))
                else:
                    first.setdefault(qid, m.start())
                    labels.setdefault(qid, set()).add(label)
                    add(qid, "lien", "lien", m.start(), _snippet(text, m.start(), m.end()))
        if not tpl_stack and not ref_depth and not file_starts:
            zone_start = m.end()
    if not tpl_stack and not ref_depth and not file_starts and zone_start < len(text):
        body.append((zone_start, len(text)))

    rows.extend(_name_mentions(text, body, first, labels, self_qid, self_name, qid_to_name, places, sections_at, n))
    return _dedupe(rows)


def _name_mentions(text, body, first, labels, self_qid, self_name, qid_to_name, places, sections_at, n) -> list[dict]:
    """Mentions sans lien des personnes déjà liées dans la page, après leur premier lien."""
    owners: dict[str, set[str]] = {}
    kinds: dict[str, str] = {}
    for qid in first:
        name = _display_name(qid_to_name.get(qid, ""))
        candidates = {name: "complet", _surname(name): "famille"}
        candidates.update({l: "libelle" for l in labels[qid] if l != name})
        for v, kind in candidates.items():
            # Un seul mot qui est aussi un lieu, un club, un prix… (« France » pour Anatole France) : ambigu.
            if v and len(v) >= 4 and v[0].isupper() and v not in places:
                owners.setdefault(v, set()).add(qid)
                kinds.setdefault(v, kind)
    self_words = set(_display_name(self_name).split())
    names = {v: next(iter(q)) for v, q in owners.items()
             if len(q) == 1 and not set(v.split()) <= self_words}
    if not names or not body:
        return []

    pattern = re.compile(r"(?<![\w-])(" + "|".join(map(re.escape, sorted(names, key=len, reverse=True))) + r")(?![\w-])")
    starts = [s for s, _ in body]
    sec_starts = [s for s, _ in sections_at]
    rows = []
    for m in pattern.finditer(text):
        qid = names[m.group(1)]
        i = bisect_right(starts, m.start()) - 1
        if m.start() <= first[qid] or i < 0 or m.end() > body[i][1]:
            continue
        line_start = text.rfind("\n", 0, m.start()) + 1
        if text[line_start:line_start + 1] in "*#;:|!":  # éléments de liste : bibliographies, filmographies
            continue
        if kinds[m.group(1)] == "famille":
            # « Jérôme Grévy » n'est pas Jules Grévy : un prénom devant le nom doit être celui de la personne.
            before = _WORD_BEFORE.search(text, max(line_start, m.start() - 40), m.start())
            if before and before.group(1)[0].isupper() and before.group(1) not in qid_to_name.get(qid, ""):
                prefix = text[line_start:before.start()].rstrip()
                if prefix and prefix[-1] not in ".!?:»\"'":  # en début de phrase, c'est « Selon », « Avec »…
                    continue
        sentence = _snippet(text, m.start(), m.end())
        if sentence:
            rows.append({"source_qid": self_qid, "target_qid": qid, "kind": "nom", "variant": kinds[m.group(1)],
                         "section": sections_at[bisect_right(sec_starts, m.start()) - 1][1],
                         "position": m.start() / n, "sentence": sentence})
    return rows


def _dedupe(rows: list[dict]) -> list[dict]:
    """Une phrase par paire et par texte (un lien et son nom dans la même phrase ne comptent qu'une fois)."""
    seen, per_pair, out = set(), {}, []
    for r in sorted(rows, key=lambda r: r["position"]):
        key = (r["target_qid"], r["sentence"][:100])  # bornes un peu différentes : même phrase
        if key in seen or per_pair.get(r["target_qid"], 0) >= MAX_PER_PAIR:
            continue
        seen.add(key)
        per_pair[r["target_qid"]] = per_pair.get(r["target_qid"], 0) + 1
        out.append(r)
    return out


# --- Traitement parallèle des blocs du dump (comme links.extract_links) -------------------

_W: dict = {}


def _init_worker(dump, title_to_qid, page_to_qid, qid_to_name, places) -> None:
    _W.update(dump=dump, title_to_qid=title_to_qid, page_to_qid=page_to_qid, qid_to_name=qid_to_name, places=places)


def _process_block(span: tuple[int, int]) -> list[dict]:
    rows = []
    for qid, text in block_pages(_W["dump"], span, _W["page_to_qid"]):
        rows.extend(page_sentences(text, _W["title_to_qid"], qid, _W["qid_to_name"].get(qid, ""), _W["qid_to_name"],
                                   _W["places"]))
    return rows


def extract_sentences(workers: int | None = None, limit: int | None = None) -> None:
    humans = pl.read_parquet(work_path("humans.parquet"))
    page_to_qid = dict(zip(humans["page_id"].to_list(), humans["qid"].to_list()))
    qid_to_name = dict(zip(humans["qid"].to_list(), humans["title"].to_list()))
    labels = pl.read_parquet(work_path("refs.parquet"), columns=["label"])["label"].drop_nulls()
    places = frozenset(labels.filter(~labels.str.contains(" ")).to_list())
    title_to_qid = human_titles(humans)
    spans, n_blocks = human_blocks(page_to_qid)
    if limit:
        spans = spans[:limit]
    print(f"{len(spans):,} blocs à lire sur {n_blocks:,}")

    dump = str(dump_path("pages-articles-multistream.xml.bz2"))
    parts = work_path("link_sentences_parts")
    if parts.exists():
        shutil.rmtree(parts)
    parts.mkdir()
    buf, total = [], 0

    def flush() -> None:
        nonlocal buf, total
        i = len(list(parts.glob("*.parquet")))
        pl.DataFrame(buf, schema=SCHEMA).write_parquet(parts / f"part-{i:05d}.parquet")
        total += len(buf)
        buf = []

    with ProcessPoolExecutor(workers or os.cpu_count(), initializer=_init_worker,
                             initargs=(dump, title_to_qid, page_to_qid, qid_to_name, places)) as pool:
        for rows in tqdm(pool.map(_process_block, spans, chunksize=64), total=len(spans), desc="blocs", unit="bloc"):
            buf.extend(rows)
            if len(buf) >= FLUSH_ROWS:
                flush()
    flush()

    out = work_path("link_sentences.parquet")
    pl.scan_parquet(parts / "*.parquet").sink_parquet(out, compression="zstd")
    shutil.rmtree(parts)
    print(f"{total:,} phrases : {out}")

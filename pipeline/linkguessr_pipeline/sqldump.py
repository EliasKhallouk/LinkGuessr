"""Lecture des dumps SQL MySQL de Wikimedia sans installer MySQL.

Les dumps contiennent un CREATE TABLE puis des `INSERT INTO `table` VALUES`
suivis des tuples `(...)`. On lit les noms de colonnes dans le CREATE TABLE
puis on extrait chaque tuple avec une regex.
"""
import gzip
import re
from collections.abc import Iterator
from pathlib import Path

_VAL = r"('(?:[^'\\]|\\.)*'|NULL|[^,'()]*)"
_ESCAPES = {"0": "\0", "n": "\n", "r": "\r", "t": "\t", "Z": "\x1a"}
_UNESCAPE = re.compile(r"\\(.)")
_COLUMN = re.compile(r"\s+`(\w+)`")


def _convert(raw: str):
    if raw == "NULL":
        return None
    if raw.startswith("'"):
        return _UNESCAPE.sub(lambda m: _ESCAPES.get(m.group(1), m.group(1)), raw[1:-1])
    try:
        return int(raw)
    except ValueError:
        return float(raw)


def read_table(path: Path, table: str, columns: list[str]) -> Iterator[tuple]:
    """Itère sur les lignes de `table`, en ne renvoyant que `columns` (dans cet ordre)."""
    create_prefix = f"CREATE TABLE `{table}`"
    insert_prefix = f"INSERT INTO `{table}` VALUES "
    all_columns: list[str] = []
    in_create = False
    row_re = None
    wanted: list[int] = []

    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith(create_prefix):
                in_create = True
                continue
            if in_create:
                if m := _COLUMN.match(line):
                    all_columns.append(m.group(1))
                elif line.startswith(")"):
                    in_create = False
                    row_re = re.compile(r"\(" + ",".join([_VAL] * len(all_columns)) + r"\)")
                    wanted = [all_columns.index(c) for c in columns]
                continue
            # Anciens dumps : tous les tuples sur la ligne de l'INSERT.
            # Dumps récents : « INSERT INTO ... VALUES » seul, puis un tuple par ligne.
            if row_re is not None and (line.startswith("(") or line.startswith(insert_prefix)):
                for m in row_re.finditer(line):
                    groups = m.groups()
                    yield tuple(_convert(groups[i]) for i in wanted)

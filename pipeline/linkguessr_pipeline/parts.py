"""Écriture de grandes tables par paquets, pour garder une RAM bornée."""
import shutil
from collections.abc import Callable
from pathlib import Path

import polars as pl


class PartWriter:
    """Accumule des lignes (dict) et les écrit en fichiers parquet de `rows` lignes,
    puis les assemble en un seul fichier sans tout recharger en mémoire."""

    def __init__(self, directory: Path, schema: dict, rows: int = 300_000):
        self.directory, self.schema, self.rows = directory, schema, rows
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)
        self.buffer: list[dict] = []
        self.count = 0
        self.parts = 0

    def add(self, row: dict) -> None:
        self.buffer.append(row)
        if len(self.buffer) >= self.rows:
            self.flush()

    def flush(self) -> None:
        if not self.buffer:
            return
        pl.DataFrame(self.buffer, schema=self.schema).write_parquet(self.directory / f"{self.parts:05d}.parquet")
        self.count += len(self.buffer)
        self.parts += 1
        self.buffer = []

    def finish(self, out: Path, transform: Callable[[pl.LazyFrame], pl.LazyFrame] | None = None) -> int:
        self.flush()
        if self.parts == 0:
            pl.DataFrame(schema=self.schema).write_parquet(out)
        else:
            frame = pl.scan_parquet(self.directory / "*.parquet")
            (transform(frame) if transform else frame).sink_parquet(out, compression="zstd")
        shutil.rmtree(self.directory)
        return self.count

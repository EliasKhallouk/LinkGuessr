"""Téléchargement des dumps Wikimedia, avec reprise et vérification SHA-1."""
import hashlib
import os
import time
from pathlib import Path

import requests
from tqdm import tqdm

from .config import DUMP_DATE, DUMPS_DIR, WIKI, dump_name, dump_path
from .http import make_session

SQL_DUMPS = ["page.sql.gz", "page_props.sql.gz", "redirect.sql.gz"]
XML_DUMPS = ["pages-articles-multistream.xml.bz2", "pages-articles-multistream-index.txt.bz2"]

MAX_RESUMES = 50  # reprises automatiques après une coupure réseau

OFFICIAL = "https://dumps.wikimedia.org"
# Miroir officiel (liste : https://dumps.wikimedia.org/mirrors.html), souvent bien plus rapide.
MIRROR = os.getenv("LG_DUMPS_MIRROR", "https://ftp.acc.umu.se/mirror/wikimedia.org/dumps")


def _url(name: str, base: str = MIRROR) -> str:
    return f"{base}/{WIKI}/{DUMP_DATE}/{name}"


def _sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def _fetch(session, url: str, part: Path) -> None:
    """Télécharge `url` dans `part`, en reprenant à la fin du fichier partiel s'il existe."""
    offset = part.stat().st_size if part.exists() else 0
    headers = {"Range": f"bytes={offset}-"} if offset else {}
    with session.get(url, headers=headers, stream=True, timeout=60) as r:
        if r.status_code == 416:  # déjà complet
            return
        r.raise_for_status()
        if r.status_code != 206:
            offset = 0
        total = offset + int(r.headers.get("Content-Length", 0))
        with part.open("ab" if offset else "wb") as f, tqdm(
            total=total, initial=offset, unit="B", unit_scale=True, desc=part.name
        ) as bar:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
                bar.update(len(chunk))


def download(suffixes: list[str]) -> None:
    DUMPS_DIR.mkdir(parents=True, exist_ok=True)
    session = make_session()
    # Les sommes de contrôle viennent toujours du serveur officiel.
    sums_text = session.get(_url(dump_name("sha1sums.txt"), OFFICIAL), timeout=60).text
    sums = {name: sha for sha, name in (line.split() for line in sums_text.splitlines() if line.strip())}

    for suffix in suffixes:
        path = dump_path(suffix)
        verified = path.with_name(path.name + ".ok")
        if path.exists() and verified.exists():
            print(f"déjà présent : {path.name}")
            continue

        part = path.with_name(path.name + ".part")
        for attempt in range(MAX_RESUMES):
            try:
                _fetch(session, _url(path.name), part)
                break
            except (requests.ConnectionError, requests.exceptions.ChunkedEncodingError) as e:
                print(f"connexion coupée ({e.__class__.__name__}), reprise {attempt + 1}/{MAX_RESUMES}")
                time.sleep(min(60, 5 * (attempt + 1)))
        else:
            raise RuntimeError(f"téléchargement de {path.name} impossible : relancer plus tard")

        print(f"vérification SHA-1 : {path.name}")
        if _sha1(part) != sums[path.name]:
            part.unlink()
            raise RuntimeError(f"SHA-1 invalide pour {path.name}, fichier supprimé : relancer")
        part.replace(path)
        verified.touch()

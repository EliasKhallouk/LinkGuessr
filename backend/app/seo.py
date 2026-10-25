"""Sitemap pour les moteurs de recherche : les pages fixes et une page par personne reliée au réseau.

Servi sous link-guessr.vercel.app/sitemap.xml (relais Vercel), découpé en fichiers de 25 000 adresses.
"""
import math

from fastapi import APIRouter, HTTPException, Response

from .core import pool, state

router = APIRouter()
SITE = "https://link-guessr.vercel.app"
PER_FILE = 25_000  # ~2,5 Mo : sous la limite de taille des réponses des fonctions Vercel
STATIC_PAGES = ["/", "/lab", "/a-propos"]
CACHE = "public, max-age=3600, s-maxage=86400"


def _lastmod() -> str:
    d = state.get("dump_date") or ""
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else ""


def _xml(body: str) -> Response:
    return Response(f'<?xml version="1.0" encoding="UTF-8"?>\n{body}\n', media_type="application/xml",
                    headers={"Cache-Control": CACHE})


def _count() -> int:
    if "sitemap_count" not in state:
        with pool.connection() as conn:
            state["sitemap_count"] = conn.execute("SELECT count(*) AS n FROM person WHERE degree > 0").fetchone()["n"]
    return state["sitemap_count"]


@router.get("/sitemap.xml")
def sitemap_index():
    files = math.ceil(_count() / PER_FILE)
    entries = [f"  <sitemap><loc>{SITE}/sitemap-pages.xml</loc></sitemap>"]
    entries += [f"  <sitemap><loc>{SITE}/sitemap-{i}.xml</loc><lastmod>{_lastmod()}</lastmod></sitemap>" for i in range(files)]
    return _xml('<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(entries) + "\n</sitemapindex>")


@router.get("/sitemap-pages.xml")
def sitemap_pages():
    urls = "\n".join(f"  <url><loc>{SITE}{p}</loc></url>" for p in STATIC_PAGES)
    return _xml(f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}\n</urlset>')


@router.get("/sitemap-{index}.xml")
def sitemap_people(index: int):
    if index < 0 or index * PER_FILE >= _count():
        raise HTTPException(404, "Sitemap inconnu")
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT qid FROM person WHERE degree > 0 ORDER BY id OFFSET %s LIMIT %s",
            (index * PER_FILE, PER_FILE),
        ).fetchall()
    lastmod = _lastmod()
    urls = "\n".join(f"  <url><loc>{SITE}/personne/{r['qid']}</loc><lastmod>{lastmod}</lastmod></url>" for r in rows)
    return _xml(f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}\n</urlset>')

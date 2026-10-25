import requests
from bs4 import BeautifulSoup, Tag, NavigableString
from urllib.parse import urljoin, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import unicodedata
from TypeOfPage import detect_wikipedia_entity_type
"""Affichage progressif optionnel via tqdm, avec repli si non installé."""
try:
    from tqdm import tqdm  # type: ignore
except Exception:
    class tqdm:
        def __init__(self, iterable=None, total=None, desc=None, unit=None, leave=False, **kwargs):
            self.iterable = iterable
        def __iter__(self):
            return iter(self.iterable) if self.iterable is not None else iter([])
        def update(self, n: int = 1):
            pass
        def set_postfix_str(self, s: str):
            pass
        def close(self):
            pass

def normalize_heading(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s.strip().lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.replace(" ", "_")

def nettoyer_sections_exclues(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    mots_cles_exclus = [
        "notes", "références", "references", "voir aussi",
        "bibliographie", "liens externes", "sources", "notes et références"
    ]

    main_div = soup.find("div", id="mw-content-text")
    if not main_div:
        return html

    # supprimer tout le contenu après la première section à exclure
    for heading in main_div.find_all(["h1","h2","h3","h4","h5"]):
        titre = normalize_heading(heading.get_text(strip=True))
        if any(mot in titre for mot in mots_cles_exclus):
            for elem in list(heading.find_all_next()):
                elem.decompose()
            break

    # sauvegarde pour debug
    #Path("soup.html").write_text(str(soup), encoding="utf-8")
    return str(soup)

def get_wikipedia_links(url: str):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()

    soup = BeautifulSoup(nettoyer_sections_exclues(r.text), "html.parser")
    base_url = f"https://{url.split('/')[2]}"
    excluded_prefixes = (
        "Fichier:", "Catégorie:", "Aide:", "Portail:",
        "Spécial:", "Discussion:", "Modèle:",
        "File:", "Category:", "Help:", "Portal:",
        "Special:", "Talk:", "Template:"
    )

    links = set()
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if href.startswith("/wiki/"):
            page_name = unquote(href.split("/wiki/", 1)[1])
            if not any(page_name.startswith(prefix) for prefix in excluded_prefixes):
                links.add(unquote(urljoin(base_url, href)))

    return sorted(links)

def filter_links_by_person(links, max_workers=5, limit=None, show_progress=True, position=None):
    if limit:
        links = list(links)[:limit]

    results = []
    errors = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(detect_wikipedia_entity_type, url): url for url in links}
        iterator = as_completed(futures)
        pbar = tqdm(total=len(futures), desc="Filtrage (personnes)", unit="lien", leave=False, position=position) if show_progress else None
        for fut in iterator:
            url = futures[fut]
            try:
                if fut.result():
                    results.append(url)
            except Exception as e:
                errors.append((url, str(e)))
            finally:
                if pbar:
                    pbar.update(1)
        if pbar:
            pbar.close()

    if errors and show_progress:
        print(f"⚠️  {len(errors)} liens ont causé des erreurs lors du filtrage (API rate limit, timeout, etc.)")

    return sorted(results)

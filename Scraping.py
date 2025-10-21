import requests
from bs4 import BeautifulSoup, Tag, NavigableString
from urllib.parse import urljoin, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import unicodedata
from TypeOfPage import detect_wikipedia_entity_type

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
    headers = {"User-Agent": "LinkGuessr/1.0 (https://github.com/EliasKhallouk/LinkGuessr) Python/requests"}
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

def filter_links_by_person(links, max_workers=10, limit=None):
    if limit:
        links = list(links)[:limit]

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(detect_wikipedia_entity_type, url): url for url in links}
        for fut in as_completed(futures):
            url = futures[fut]
            try:
                if fut.result():
                    results.append(url)
            except Exception:
                pass

    return sorted(results)

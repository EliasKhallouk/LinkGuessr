import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote
from TypeOfPage import detect_wikipedia_entity_type
from concurrent.futures import ThreadPoolExecutor, as_completed


def get_wikipedia_links(url):
    """Récupère tous les liens internes d'une page Wikipédia (bruts, pas filtrés).

    Ne filtre pas encore par type; on collecte d'abord les URLs puis on les
    traite en parallèle si nécessaire. Cela évite d'appeler detect_* pour
    chaque balise et améliore la clarté.
    """
    headers = {
        "User-Agent": "LinkGuessr/1.0 (https://github.com/EliasKhallouk/LinkGuessr; contact@example.com) Python/requests"
    }
    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")


    base_url = f"https://{url.split('/')[2]}"  # ex: fr.wikipedia.org

    excluded_prefixes = (
        "Fichier:", "Catégorie:", "Aide:", "Portail:", 
        "Spécial:", "Discussion:", "Modèle:",
        "File:", "Category:", "Help:", "Portal:",
        "Special:", "Talk:", "Template:"
    )
    
    links = set()  # Collecte des liens uniques (evite les doublons)
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        # On garde seulement les liens internes de type /wiki/...
        if href.startswith("/wiki/"):
            # Décode l'URL pour vérifier les préfixes
            decoded_href = unquote(href)
            # Extrait la partie après /wiki/
            page_name = decoded_href.split("/wiki/", 1)[1] if "/wiki/" in decoded_href else ""
            
            # Vérifie si le lien commence par un préfixe exclu
            if not any(page_name.startswith(prefix) for prefix in excluded_prefixes):
                # Construit l'URL complète et la décode
                full_url = urljoin(base_url, href)
                decoded_full_url = unquote(full_url)
                links.add(decoded_full_url)

    return sorted(links)


def filter_links_by_person(links, max_workers=10, limit=None):
    """Filtre la liste de liens pour ne garder que ceux représentant des personnes.

    - links: iterable d'URLs
    - max_workers: nombre de threads pour la vérification
    - limit: si défini, limite le nombre de liens à traiter (utile pour testing)
    """
    if limit:
        links = list(links)[:limit]

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(detect_wikipedia_entity_type, url): url for url in links}
        for fut in as_completed(futures):
            url = futures[fut]
            try:
                is_person = fut.result()
            except Exception:
                is_person = False
            if is_person:
                results.append(url)

    return sorted(results)

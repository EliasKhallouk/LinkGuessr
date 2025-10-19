import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote
from pathlib import Path
from TypeOfPage import detect_wikipedia_entity_type
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial


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

    # Temporary: save the soup to a file for debugging
    output_path = Path(__file__).resolve().parent / "soup.html"
    output_path.write_text(soup.prettify(), encoding="utf-8")
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
            except Exception as e:
                # En cas d'erreur, on ignore ou on peut logger
                is_person = False
            if is_person:
                results.append(url)

    return sorted(results)

# ==========================
# 🔍 Exemple d’utilisation
# ==========================
if __name__ == "__main__":
    url = "https://fr.wikipedia.org/wiki/Emmanuel_Macron"
    result = get_wikipedia_links(url)

    print(f"🔗 {len(result)} liens trouvés sur {url}\n")
    output_path = Path(__file__).resolve().parent / "all_links.txt"
    # Ouvre en mode 'w' pour écraser le contenu existant
    with output_path.open("w", encoding="utf-8") as f:
        # Décode les URLs pour afficher correctement les caractères accentués
        decoded_links = [unquote(link) for link in result]
        f.write("\n".join(decoded_links))
    #for link in result:  # on affiche les 20 premiers
     #   print(link)

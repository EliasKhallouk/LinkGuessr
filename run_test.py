import time
import os
from urllib.parse import unquote
from Scraping import get_wikipedia_links, filter_links_by_person
from neo4j import GraphDatabase
from dotenv import load_dotenv
"""Ajout d'une barre de progression console (tqdm) avec repli gracieux.
Si tqdm n'est pas installé, le code fonctionne sans affichage.
"""
try:
    from tqdm import tqdm  # type: ignore
except Exception:  # pas de dépendance dure à tqdm
    class tqdm:  # léger stub compatible avec l'API utilisée
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

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def add_person_with_relation(tx, main_name, person_name):
    tx.run("""
        MERGE (a:Person {name: $main_name})
        MERGE (b:Person {name: $person_name})
        MERGE (a)-[:CONNAIT]->(b)
    """, main_name=main_name, person_name=person_name)

def get_person_name_from_url(url):
    """Convertit une URL Wikipedia en nom propre proprement formaté"""
    return unquote(url.split('/')[-1])

def crawl_person(url, depth=1, max_depth=2, visited=None, base_pos=0):
    """Explore récursivement les relations jusqu'à max_depth.

    IMPORTANT: visited tracks page *names* (titles), not raw URLs, to avoid
    créer des boucles causées par variantes d'URL. On n'insère jamais d'URL
    dans la BDD — seulement les noms (labels) extraits par
    `get_person_name_from_url`.
    """
    if visited is None:
        visited = set()

    if depth > max_depth:
        return

    main_name = get_person_name_from_url(url)
    # éviter de réexplorer le même nom
    if main_name in visited:
        return
    visited.add(main_name)

    print(f"{'  ' * (depth - 1)}➡️  Niveau {depth}: {main_name}")

    links = get_wikipedia_links(url)

    people = filter_links_by_person(links, max_workers=20, show_progress=True, position=base_pos + 1)
    print(len(people), "personnes trouvées sur la page.")
    # Ajout des relations avec barre de progression
    with driver.session() as session:
        for link in tqdm(people, desc=f"Relations (niveau {depth})", unit="pers.", leave=False, position=base_pos + 1):
            person_name = get_person_name_from_url(link)
            # éviter la relation vers soi-même
            if person_name == main_name:
                continue
            session.execute_write(add_person_with_relation, main_name, person_name)

    # récursion sur les personnes trouvées (on passe l'URL d'origine de la personne)
    # Exploration récursive des personnes trouvées avec barre de progression
    pbar = tqdm(total=len(people), desc=f"Exploration niveau {depth + 1}", unit="pers.", leave=False, position=base_pos)
    for link in people:
        current = get_person_name_from_url(link)
        try:
            pbar.set_postfix_str(current)
        except Exception:
            pass
        crawl_person(link, depth + 1, max_depth, visited, base_pos=base_pos + 1)
        pbar.update(1)
    pbar.close()

if __name__ == "__main__":
    start_url = "http://fr.wikipedia.org/wiki/Squeezie"
    t0 = time.time()
    crawl_person(start_url, max_depth=2)
    print(f"Exploration complète en {time.time() - t0:.2f}s ✅")
    #print(get_person_name_from_url("https://fr.wikipedia.org/wiki/Prince_(musicien)"))
    


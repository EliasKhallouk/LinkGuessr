import time
import os
from urllib.parse import unquote
from Scraping import get_wikipedia_links, filter_links_by_person
from neo4j import GraphDatabase
from dotenv import load_dotenv

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

def crawl_person(url, depth=1, max_depth=2, visited=None):
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
    print(len(links), "liens trouvés sur la page.")
    people = filter_links_by_person(links, max_workers=20)

    with driver.session() as session:
        for link in people:
            person_name = get_person_name_from_url(link)
            # éviter la relation vers soi-même
            if person_name == main_name:
                continue
            session.execute_write(add_person_with_relation, main_name, person_name)

    # récursion sur les personnes trouvées (on passe l'URL d'origine de la personne)
    for link in people:
        crawl_person(link, depth + 1, max_depth, visited)

if __name__ == "__main__":
    start_url = "https://fr.wikipedia.org/wiki/Karim_Benzema"
    t0 = time.time()
    crawl_person(start_url, max_depth=2)
    print(f"Exploration complète en {time.time() - t0:.2f}s ✅")
    #print(get_person_name_from_url("https://fr.wikipedia.org/wiki/Prince_(musicien)"))
    


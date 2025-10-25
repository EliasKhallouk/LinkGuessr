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

def crawl_person(url, depth=1, max_depth=2, visited=None, base_pos=0, chain=None):
    """Explore récursivement les relations jusqu'à max_depth.

    IMPORTANT: visited tracks page *names* (titles), not raw URLs, to avoid
    créer des boucles causées par variantes d'URL. On n'insère jamais d'URL
    dans la BDD — seulement les noms (labels) extraits par
    `get_person_name_from_url`.
    """
    if visited is None:
        visited = set()
    # Historique des ancêtres pour une meilleure lisibilité
    # chain=[Niveau1, Niveau2, ..., Courant]
    if chain is None:
        chain = []

    if depth > max_depth:
        return

    main_name = get_person_name_from_url(url)
    # éviter de réexplorer le même nom
    if main_name in visited:
        return
    visited.add(main_name)

    # Pas de barre ici: une seule barre est affichée au niveau racine (N1)

    # Construit la chaîne d'ancêtres à afficher (racine > ... > courant)
    current_chain = chain + [main_name]
    racine = current_chain[0] if current_chain else main_name
    indent = "  " * (depth - 1)
    # Affichage uniquement pour la racine (N+1)
    if depth == 1:
        print(f"➡️  Racine (N1): {main_name}")

    links = get_wikipedia_links(url)

    people = filter_links_by_person(links, max_workers=20, show_progress=False, position=None)
    if depth == 1:
        print(f"📎 {len(people)} personnes trouvées sur: {main_name}")
    # Ajout des relations avec barre de progression
    with driver.session() as session:
        for link in people:
            person_name = get_person_name_from_url(link)
            # éviter la relation vers soi-même
            if person_name == main_name:
                continue
            session.execute_write(add_person_with_relation, main_name, person_name)

    # récursion sur les personnes trouvées (on passe l'URL d'origine de la personne)
    # Exploration récursive des personnes trouvées avec barre de progression
    # Si on est à la racine, on affiche UNE seule barre dont le total
    # est le nombre d'enfants directs (N2). La barre avance quand on a
    # terminé de parcourir chaque enfant et son sous-graphe.
    if depth == 1:
        pbar = tqdm(total=len(people), desc=f"Exploration N2 de {main_name}", unit="page", leave=True)
        for link in people:
            crawl_person(link, depth + 1, max_depth, visited, base_pos=base_pos + 1, chain=current_chain)
            try:
                pbar.update(1)
            except Exception:
                pass
        try:
            pbar.close()
        except Exception:
            pass
    else:
        # Pour N>=2, on explore silencieusement (pas de barre ni de logs verbeux)
        for link in people:
            crawl_person(link, depth + 1, max_depth, visited, base_pos=base_pos + 1, chain=current_chain)

if __name__ == "__main__":
    start_urls = [
        "http://fr.wikipedia.org/wiki/Anyme023",
        "http://fr.wikipedia.org/wiki/Elon_Musk",
        "http://fr.wikipedia.org/wiki/Jeff_Bezos",
        "http://fr.wikipedia.org/wiki/Bill_Gates",
    ]

    t0 = time.time()
    # si vous voulez éviter de re-parcourir les mêmes personnes entre URLs,
    # conservez un ensemble `visited` partagé ; sinon passez None dans crawl_person
    visited_global = set()

    for url in start_urls:
        racine_nom = get_person_name_from_url(url)
        print("\n" + "=" * 60)
        print(f"🚀 Démarrage racine: {racine_nom} | URL: {url}")
        print("=" * 60)
        crawl_person(url, max_depth=2, visited=visited_global, chain=[])

    print(f"Exploration complète en {time.time() - t0:.2f}s ✅")






##########################################
#   LISTE DES PERONNES DEJA AJOUTÉES :   #
##########################################

# YOUTUBEURS:
# "http://fr.wikipedia.org/wiki/Squeezie",
# "http://fr.wikipedia.org/wiki/Kameto",
# "http://fr.wikipedia.org/wiki/Michou_(vidéaste)",

# SPORTIFS:
# "http://fr.wikipedia.org/wiki/Karim_Benzema",
# "http://fr.wikipedia.org/wiki/Mohamed_Ali",

# MUSICIENS:
# "http://fr.wikipedia.org/wiki/Taylor_Swift",
# "http://fr.wikipedia.org/wiki/Travis_Scott",

# AUTEUR :
# "http://fr.wikipedia.org/wiki/Akira_Toriyama",

# ACTEURS:
# "http://fr.wikipedia.org/wiki/Will_Smith",
# "http://fr.wikipedia.org/wiki/Gad_Elmaleh",


# SCIENTIFIQUES:
# "http://fr.wikipedia.org/wiki/Albert_Einstein",
# "http://fr.wikipedia.org/wiki/Marie_Curie",
# "http://fr.wikipedia.org/wiki/Léonard_de_Vinci",
# "http://fr.wikipedia.org/wiki/Isaac_Newton",

# POLITIQUES:
# "http://fr.wikipedia.org/wiki/Emmanuel_Macron",
# "http://fr.wikipedia.org/wiki/Adolf_Hitler",

##########################################
#     LISTE DES PERONNES A AJOUTÉES :    #
##########################################


#"http://fr.wikipedia.org/wiki/Mark_Zuckerberg",
#"http://fr.wikipedia.org/wiki/Steve_Jobs",
#"http://fr.wikipedia.org/wiki/Beyoncé",
#"http://fr.wikipedia.org/wiki/Rihanna",
#"http://fr.wikipedia.org/wiki/Kanye_West",
#"http://fr.wikipedia.org/wiki/Drake_(rappeur)",
#"http://fr.wikipedia.org/wiki/Donald_Trump",
#"http://fr.wikipedia.org/wiki/Barack_Obama",
#"http://fr.wikipedia.org/wiki/Daft_Punk",

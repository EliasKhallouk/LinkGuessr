import time
import os
from urllib.parse import unquote
from Scraping import get_wikipedia_links, filter_links_by_person
from TypeOfPage import detect_wikipedia_entity_type, classify_person
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

def ensure_person_node(tx, person_name):
    tx.run("""
        MERGE (b:Person {name: $person_name})
    """, person_name=person_name)

def upsert_person_metadata(tx, node_name, categories):
    """Ajoute ou met à jour les métadonnées d'une personne.

    - node_name: identifiant unique utilisé dans le graphe (slug wiki avec underscores)
    - display_name: libellé humain (avec espaces/accents) issu de Wikidata
    - categories: liste[str] (categorie_generale)
    """
    tx.run(
        """
        MERGE (p:Person {name: $name})
        SET p.categorie_generale = $categories
        """,
        name=node_name,
        categories=categories,
    )

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
    # Ajout des relations ou des nœuds selon le type du courant (personne ou non)
    try:
        current_is_person = detect_wikipedia_entity_type(url)
    except Exception:
        current_is_person = False

    with driver.session() as session:
        # Si le courant est une personne, classifier et insérer ses métadonnées
        if current_is_person:
            classification = classify_person(url)
            if classification:
                try:
                    session.execute_write(
                        upsert_person_metadata,
                        main_name,  # MERGE par slug/underscore
                        classification.get("categorie_generale", []),
                    )
                except Exception:
                    pass

        if current_is_person:
            # le courant est une PERSONNE: relier courant -> personnes trouvées (N+1)
            for link in people:
                person_name = get_person_name_from_url(link)
                if person_name == main_name:
                    continue
                session.execute_write(add_person_with_relation, main_name, person_name)
                # Tenter de classifier les enfants directs (utile pour remplir la BDD)
                try:
                    child_cls = classify_person(link)
                    if child_cls:
                        session.execute_write(
                            upsert_person_metadata,
                            person_name,  # MERGE par slug/underscore
                            child_cls.get("categorie_generale", []),
                        )
                except Exception:
                    pass
        else:
            # le courant n'est PAS une personne (ex: série): ne PAS créer de nœud courant
            # mais on crée les nœuds enfants (personnes N+1) sans relation depuis le courant
            for link in people:
                person_name = get_person_name_from_url(link)
                session.execute_write(ensure_person_node, person_name)
                # Classifier et stocker leurs métadonnées également
                try:
                    child_cls = classify_person(link)
                    if child_cls:
                        session.execute_write(
                            upsert_person_metadata,
                            person_name,  # MERGE par slug/underscore
                            child_cls.get("categorie_generale", []),
                        )
                except Exception:
                    pass

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
        "https://fr.wikipedia.org/wiki/Emmanuel_Macron",

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

    elapsed = int(time.time() - t0)
    hrs, rem = divmod(elapsed, 3600)
    mins, secs = divmod(rem, 60)
    print(f"Exploration complète en {hrs:02d}:{mins:02d}:{secs:02d} ✅")






##########################################
#   LISTE DES PERONNES DEJA AJOUTÉES :   #
##########################################

# YOUTUBEURS:
# "http://fr.wikipedia.org/wiki/Squeezie",
# "http://fr.wikipedia.org/wiki/Kameto",
# "http://fr.wikipedia.org/wiki/Michou_(vidéaste)",
# "http://fr.wikipedia.org/wiki/Anyme023",
# "https://fr.wikipedia.org/wiki/MrBeast",

# SPORTIFS:
# "http://fr.wikipedia.org/wiki/Karim_Benzema",
# "http://fr.wikipedia.org/wiki/Mohamed_Ali",
# "https://fr.wikipedia.org/wiki/Lamine_Yamal",
# "https://fr.wikipedia.org/wiki/Kylian_Mbappé",
# "https://fr.wikipedia.org/wiki/Cristiano_Ronaldo",
# "https://fr.wikipedia.org/wiki/Teddy_Riner",
# "https://fr.wikipedia.org/wiki/Léon_Marchand",
# "https://fr.wikipedia.org/wiki/Lionel_Messi",
# "https://fr.wikipedia.org/wiki/Michael_Jordan",

# MUSICIENS:
# "http://fr.wikipedia.org/wiki/Taylor_Swift",
# "http://fr.wikipedia.org/wiki/Travis_Scott",
# "http://fr.wikipedia.org/wiki/Beyoncé",
# "http://fr.wikipedia.org/wiki/Rihanna",
# "http://fr.wikipedia.org/wiki/Kanye_West",
# "http://fr.wikipedia.org/wiki/Drake_(rappeur)",
# "http://fr.wikipedia.org/wiki/Daft_Punk",
# "https://fr.wikipedia.org/wiki/Aya_Nakamura",
# "https://fr.wikipedia.org/wiki/Bob_Marley",
# "https://fr.wikipedia.org/wiki/Michael_Jackson",
# "https://fr.wikipedia.org/wiki/XXXTentacion",

# AUTEUR :
# "http://fr.wikipedia.org/wiki/Akira_Toriyama",

# ACTEURS:
# "http://fr.wikipedia.org/wiki/Will_Smith",
# "http://fr.wikipedia.org/wiki/Gad_Elmaleh",
# "https://fr.wikipedia.org/wiki/Leonardo_DiCaprio",

# SCIENTIFIQUES:
# "http://fr.wikipedia.org/wiki/Albert_Einstein",
# "http://fr.wikipedia.org/wiki/Marie_Curie",
# "http://fr.wikipedia.org/wiki/Léonard_de_Vinci",
# "http://fr.wikipedia.org/wiki/Isaac_Newton",
# "https://fr.wikipedia.org/wiki/Stephen_Hawking",

# POLITIQUES:
# "http://fr.wikipedia.org/wiki/Emmanuel_Macron",
# "http://fr.wikipedia.org/wiki/Donald_Trump",
# "http://fr.wikipedia.org/wiki/Barack_Obama",
# "https://fr.wikipedia.org/wiki/Jordan_Bardella",
# "https://fr.wikipedia.org/wiki/Gabriel_Attal",
# "https://fr.wikipedia.org/wiki/Jean-Luc_Mélenchon",
# "https://fr.wikipedia.org/wiki/Michel_Barnier",
# "https://fr.wikipedia.org/wiki/François_Hollande",
# "https://fr.wikipedia.org/wiki/François_Bayrou",
# "https://fr.wikipedia.org/wiki/Sébastien_Lecornu",
# "https://fr.wikipedia.org/wiki/Jean_Castex",

# MILLIONAIRES TECH:
# "http://fr.wikipedia.org/wiki/Elon_Musk",
# "http://fr.wikipedia.org/wiki/Jeff_Bezos",
# "http://fr.wikipedia.org/wiki/Bill_Gates",
# "http://fr.wikipedia.org/wiki/Mark_Zuckerberg",
# "http://fr.wikipedia.org/wiki/Steve_Jobs",

# JOURNALISTES:
# "https://en.wikipedia.org/wiki/Charlie_Kirk",
# "https://fr.wikipedia.org/wiki/Edwy_Plenel",
# "https://fr.wikipedia.org/wiki/Fabrice_Arfi",
# "https://fr.wikipedia.org/wiki/Jean-Pierre_Elkabbach",
# "https://fr.wikipedia.org/wiki/Alain_Duhamel",
# "https://fr.wikipedia.org/wiki/Candace_Owens",       
# "https://fr.wikipedia.org/wiki/Amélie_Nothomb",

# HISTORIQUES:
# "https://fr.wikipedia.org/wiki/Napoléon_Ier",
# "http://fr.wikipedia.org/wiki/Adolf_Hitler",

# PAGE:
# "https://fr.wikipedia.org/wiki/Validé",


##########################################
#     LISTE DES PERONNES A AJOUTÉES :    #
##########################################

# macron en n+2 !!!!!!!!!!!










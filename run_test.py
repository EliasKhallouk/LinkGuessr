import time
import os
from urllib.parse import unquote
from Scraping import get_wikipedia_links, filter_links_by_person
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load environment variables from .env file
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

if __name__ == "__main__":
    url = "https://fr.wikipedia.org/wiki/Emmanuel_Macron"
    print("Collecting links...")
    links = get_wikipedia_links(url)
    print(f"Total links collected: {len(links)}")

    print("Filtering people...")
    people = filter_links_by_person(links, max_workers=20)

    with driver.session() as session:
        for link in people:
            person_name = unquote(link.split('/')[-1]).replace('_', ' ')
            session.execute_write(add_person_with_relation, "Emmanuel Macron", person_name)

    print(f"{len(people)} relations ajoutées avec Emmanuel Macron ✅")
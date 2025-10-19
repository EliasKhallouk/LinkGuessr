from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

app = FastAPI()

# Autoriser le front-end à accéder à l'API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/graph")
def get_graph():
    query = """
    MATCH (a:Person)-[r:CONNAIT]->(b:Person)
    RETURN a.name AS from, b.name AS to LIMIT 50
    """
    print(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

    with driver.session() as session:
        result = session.run(query)
        nodes_set = set()
        edges = []

        for record in result:
            from_name = record["from"]
            to_name = record["to"]
            nodes_set.add(from_name)
            nodes_set.add(to_name)
            edges.append({"from": from_name, "to": to_name})

        nodes = [{"id": name, "label": name} for name in nodes_set]
        return {"nodes": nodes, "edges": edges}

from fastapi import Query

@app.get("/shortest_path")
def shortest_path(person1: str = Query(...), person2: str = Query(...)):
    query = """
    MATCH p = shortestPath((a:Person {name: $person1})-[:CONNAIT*]-(b:Person {name: $person2}))
    RETURN length(p) AS nb_relations, [n IN nodes(p) | n.name] AS chemin LIMIT 50
    """
    with driver.session() as session:
        record = session.run(query, person1=person1, person2=person2).single()
        if record:
            return {"nb_relations": record["nb_relations"], "chemin": record["chemin"]}
        else:
            return {"nb_relations": None, "chemin": []}

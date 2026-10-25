# LinkGuessr

Jeux et exploration du réseau des personnes de Wikipédia FR : combien de liens séparent deux personnes,
qui se cache sur le chemin, et ce que ces liens veulent dire (page « Lab »).

## Structure

| Dossier | Contenu |
|---|---|
| `pipeline/` | Construction des données : dumps frwiki + Wikidata → fiches, liens, graphe → Postgres |
| `backend/` | API FastAPI + graphe en mémoire pour les plus courts chemins *(à venir, phase 3)* |
| `frontend/` | Site React, hébergé sur Vercel |
| `infra/vm/` | Installation de la VM Oracle (Postgres, Nginx, HTTPS) |
| `legacy/` | Ancienne version (scraping HTML, Neo4j), gardée pour comparaison |

## Architecture

```
Vercel : front React
   │ HTTPS
VM Oracle (linkguessr.duckdns.org) : Nginx → FastAPI (graphe en RAM) → PostgreSQL
   ▲
PC local : pipeline (dumps Wikimedia, Wikidata) → tables parquet → `lg load`
```

Le calcul lourd (lecture du dump de 7 Go, métriques du graphe) se fait sur un PC ;
la VM (1 cœur, 6 Go) ne fait que servir les données.

Voir [pipeline/README.md](pipeline/README.md) pour reconstruire les données.

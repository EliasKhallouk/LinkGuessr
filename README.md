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

## Outils hors ligne (`backend/tools/`)

| Script | Rôle |
|---|---|
| `load_test.py` | Test de charge (débit, latences, CPU de la VM) → rapport Markdown. Voir `docs/test-de-charge-2026-10-25.md`. |
| `surprises.py` | Paires surprenantes : deux personnes très connues, éloignées (domaine, époque), à 2 ou 3 liens, avec les phrases. `--tendances` : pics de pages vues et défis du jour possibles autour. |

```bash
cd backend
uv run python tools/surprises.py --final ../pipeline/data/work/20261001/final --top 2000 --out surprises.json
uv run python tools/surprises.py --final ../pipeline/data/work/20261001/final --tendances --out tendances.json
```

Défis du jour (sur la VM, environnement de l'API) : `python -m app.daily show`, `generate`, `set AAAA-MM-JJ --answer Q…`.

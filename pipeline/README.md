# Pipeline de données

Construit le graphe des personnes de Wikipédia FR à partir des dumps Wikimedia et de Wikidata.
Pas de scraping HTML : tout vient de fichiers officiels ou d'API publiques, avec un User-Agent identifiable.

## Installation

```bash
# uv : https://docs.astral.sh/uv/ (installe aussi Python 3.12)
cd pipeline
uv sync
```

## Étapes (dans l'ordre)

| Commande | Durée indicative | Ce qu'elle fait |
|---|---|---|
| `uv run lg download all` | ~1 h (8 Go) | Dumps frwiki : `page`, `page_props`, `redirect` (SQL) et texte des articles (XML multistream) |
| `uv run lg pages` | ~5 min | Articles de l'espace principal, leur QID Wikidata, redirections |
| `uv run lg humans` | ~30 min | Garde les articles dont le QID est un humain (P31 = Q5), via SPARQL par lots |
| `uv run lg entities` | quelques heures | Fiches Wikidata complètes (sans références), reprise automatique |
| `uv run lg refs` | ~30 min | Lieux, professions, clubs, prix… cités, + hiérarchie des professions |
| `uv run lg links` | ~20 min (8 cœurs) | Liens entre personnes dans le texte des articles, avec contexte |
| `uv run lg build` | ~10 min | Fiches structurées, faits datés, relations typées |
| `uv run lg graph` | ~5 min | Identifiants, arêtes pondérées, degré, PageRank, communautés, popularité |
| `DATABASE_URL=... uv run lg load` | ~10 min | Charge les tables finales dans Postgres (échange de schéma sans coupure) |

Les données vont dans `pipeline/data/` (ignoré par git). Date du dump : variable `LG_DUMP_DATE` (défaut dans `config.py`).

## Modèle de données

- **Fiche personne** : identité, dates avec leur précision, lieux et pays, nationalités, professions, domaines
  (taxonomie maison via la hiérarchie P279), image, identifiants externes, notoriété, introduction de l'article.
- **Faits datés** (`fact`) : fonctions, partis, clubs, formation, employeurs, distinctions… avec début et fin.
- **Liens textuels** (`text_link`) : A cite B dans le corps de son article. Nombre de mentions, section,
  présence dans l'introduction ou l'infobox, phrase de contexte. Les notes `<ref>` et les palettes sont exclues.
- **Relations Wikidata** (`relation`) : famille, couple, élève/maître, influence, successions dans une fonction.
- **Arêtes** (`edge`) : fusion non orientée des deux précédents, pondérée, utilisée pour les plus courts chemins.

## Antivirus (Windows)

Avast intercepte le TLS. `uv` utilise les certificats du système (`native-tls` dans `pyproject.toml`)
et le pipeline aussi (`truststore`). Avast définit aussi `SSLKEYLOGFILE`, ignoré par `http.py`
car il fait planter OpenSSL.

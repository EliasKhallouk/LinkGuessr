# LinkGuessr

Jeux sur le réseau des personnalités de Wikipédia FR (≈ 765 000 personnes reliées par leurs articles).
Site : https://linkguessr.com (www et link-guessr.vercel.app redirigent dessus, paramètres conservés).

## Architecture

```
Navigateur ── linkguessr.com (Vercel : front React + middleware + /api/og)
                 ├─ /v1/*     → api/proxy.js → VM (API, réponses mises en cache par Vercel)
                 └─ /umami/*  → VM (Umami, mesure d'audience sans cookie)
VM Oracle (linkguessr.duckdns.org, ARM, 1 cœur, 6 Go) : Nginx → FastAPI (graphe en RAM) → PostgreSQL
                                                       Nginx → Umami v3 (service umami, base « umami »)
PC local : pipeline (dumps frwiki + Wikidata) → parquet → `lg load` dans Postgres
```

## Stack

- `frontend/` : React 19, Vite 7, react-router 6, vis-network, chart.js. Middleware Vercel (Node) pour
  les balises d'aperçu et le SEO, `api/og.js` (@vercel/og) pour les images de partage.
- `backend/` : Python 3.12, FastAPI, psycopg, numpy (plus courts chemins en mémoire), uv.
- `pipeline/` : Python 3.12, polars, pyarrow, uv ; CLI `lg`.
- `infra/vm/` : scripts d'installation et de déploiement de la VM (bash, systemd, sans Docker).

## Commandes

```bash
cd frontend && npm install && npm run dev      # dev (Vite relaie /v1 vers l'API, voir vite.config.js)
cd frontend && npm run build                   # build ; le déploiement Vercel se fait au push sur main
cd backend && uv run pytest                    # tests de l'API
bash infra/vm/deploy.sh                        # déploie le code COMMITÉ (backend, pipeline, infra) sur la VM (ssh ek-hub)
sudo bash infra/vm/install_umami.sh            # sur la VM : installe / met à jour Umami
cd pipeline && uv run lg <étape>               # préparation des données, ordre et durées : pipeline/README.md
python -m app.daily show|generate|set …        # sur la VM : défis du jour
```

## Conventions

- Textes en français, **tutoiement partout** (interface, partage, messages d'erreur de l'API).
- Crédits et licences : textes Wikipédia CC BY-SA 4.0, données Wikidata CC0, images Wikimedia Commons avec
  auteur et licence lus en direct (`ImageCredit.jsx`, `lib/commons.js`). Toujours citer la source.
- Pas de publicité, pas de comptes, pas de cookie. Mesure d'audience : Umami auto-hébergé + événements
  anonymes vers `/events` (tableau `/admin`). Aucune donnée personnelle. Convention : `docs/tracking.md` ;
  toutes les adresses, liens générés et liens de promotion : `docs/liens.md`.
- VM à 1 cœur : ménager le CPU (cache Vercel devant l'API, limites de débit dans `policy.py`, calcul lourd
  fait sur le PC, compilations en `nice`).
- Commentaires courts en français ; commits en français, un sujet par commit.

## Fichiers clés

| Jeu | Route | Front | API |
|---|---|---|---|
| Explorer (chemins entre deux personnes) | `/explorer` | `components/Game.jsx`, `Graph.jsx`, `PathView.jsx` | `main.py` (`/path`) |
| Qui est caché ? | `/qui-est-cache` | `components/GuessWhoPath.jsx` | `main.py` (`/random_path`), `clues.py`, `eras.py` |
| Relier | `/relier` | `components/ConnectRelay.jsx` | `main.py` (`/neighbors`, `/random_pair`) |
| Combien ? | `/combien` | `components/GuessRelations.jsx`, `Leaderboard.jsx` | `game.py` |
| Défi du jour | `/`, `/jour/:n` | `components/DailyChallenge.jsx`, `pages/DailyPage.jsx` | `daily.py` |
| Duels | `/defi?jeu=…` | `pages/Duel.jsx`, `lib/share.js` | `duel.py` (jetons chiffrés, clé `DUEL_KEY`), `main.py` (`/duel/*`) |

Transverse : `frontend/src/games.jsx` (liste des jeux), `i18n/translations.js` (textes), `lib/tracking.js`
(mesure), `middleware.js` (aperçus), `vercel.json` (relais, redirections), `backend/app/admin.py`
(retours, tableau de bord), `seo.py` (sitemap), `moderation.py`, `policy.py`.

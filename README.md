# LinkGuessr

Ce dépôt contient le backend (FastAPI + Neo4j) et le frontend (React). Ce guide explique comment déployer le backend de A à Z.

## 1) Prérequis

- Python 3.11+ recommandé
- Neo4j (hébergé ou local) avec un utilisateur ayant accès en lecture aux données
- Accès shell au serveur cible (Linux), ou une machine locale pour tests

## 2) Préparer l'environnement Python

Depuis la racine du projet:

```bash
# Créer et activer un environnement virtuel (ex: venv)
python3 -m venv .venv
source .venv/bin/activate

# Installer les dépendances du projet (backend + outils de scraping)
pip install -r requirements.txt
```

Le fichier `requirements.txt` de la racine inclut:
- un include de `backend/requirements.txt` (FastAPI, Uvicorn, Neo4j, python-dotenv, pydantic)
- les dépendances pour les scripts de scraping: `requests`, `beautifulsoup4`, `tqdm` (optionnel)

## 3) Variables d'environnement (backend)

Le backend lit ses variables depuis l'environnement (via `python-dotenv`). Créez un fichier `.env` à la racine du projet (même dossier que `backend/`):

```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=motdepasse

# Chemin du fichier de classement (optionnel)
LEADERBOARD_PATH=backend/leaderboard.json

# Règles du leaderboard (optionnel)
LEADERBOARD_MAX_ENTRIES_PER_NAME=3
LEADERBOARD_MIN_SECONDS_BETWEEN=10
LEADERBOARD_NAME_MAX_LENGTH=16
```

Adaptez `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` à votre instance Neo4j.
Si vous utilisez Neo4j Aura, privilégiez un URI sécurisé (`neo4j+s://` ou `bolt+s://`).

## 4) Lancer en développement (local)

Depuis la racine du projet (après activation du venv):

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

L'API sera accessible sur `http://127.0.0.1:8000`.

Routes principales:
- `GET /graph` – retourne la liste des personnes et relations (pour le frontend)
- `GET /shortest_path?person1=...&person2=...` – plus court chemin + nombre de relations
- `GET /leaderboard` – consulter le classement
- `POST /submit_score` – enregistrer un score

## 5) Lancer en production (service systemd)

Exemple de service systemd pour héberger l'API avec Uvicorn sur un serveur Linux.

1. Créez un script de démarrage `run_backend.sh` (optionnel):

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/LinkGuessr  # chemin vers votre dépôt
source .venv/bin/activate
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Donnez-lui les droits d'exécution: `chmod +x run_backend.sh`.

2. Fichier de service `/etc/systemd/system/linkguessr.service`:

```
[Unit]
Description=LinkGuessr Backend
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/ubuntu/LinkGuessr
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=/home/ubuntu/LinkGuessr/.env
ExecStart=/home/ubuntu/LinkGuessr/.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always
User=ubuntu
Group=ubuntu

[Install]
WantedBy=multi-user.target
```

Adaptez les chemins/utilisateur selon votre serveur. Ensuite:

```bash
sudo systemctl daemon-reload
sudo systemctl enable linkguessr
sudo systemctl start linkguessr
sudo systemctl status linkguessr
```

## 6) Reverse proxy (Nginx)

Pour exposer l'API publiquement en HTTPS, placez un Nginx en frontal.

Bloc serveur d'exemple (HTTP vers l'API locale 8000):

```
server {
    listen 80;
    server_name api.votredomaine.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Ajoutez ensuite un certificat (Let's Encrypt/certbot) pour le HTTPS.

## 7) Vérifier l'accès CORS

Le backend autorise par défaut toutes les origines (CORS) pour simplifier le dev:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

En production, restreignez `allow_origins` aux domaines de votre frontend.

## 8) Déploiement alternatif: Docker (optionnel)

Un `Dockerfile` minimal pour le backend:

```
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY . /app
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build & run:

```bash
docker build -t linkguessr-backend .
docker run -d --name linkguessr -p 8000:8000 --env-file .env linkguessr-backend
```

## 9) Dépannage

- Vérifiez que Neo4j est joignable depuis le serveur (port 7687 pour Bolt).
- Si l'API ne démarre pas: vérifiez `.env` (URI, identifiants), et les logs systemd (`journalctl -u linkguessr -f`).
- Pour les erreurs CORS: resserrez/ajustez `allow_origins`.
- Pour le leaderboard: assurez-vous que `LEADERBOARD_PATH` est accessible en écriture par l'utilisateur du service.

---

## Frontend (rappel rapide)

Lancer le frontend en dev:

```bash
cd frontend
npm install
npm start
```

Configuration de l'URL de l'API:

- Le frontend lit `REACT_APP_API_BASE_URL` (ex: `http://127.0.0.1:8000`).
- Définissez-la dans `frontend/.env` ou utilisez un symlink depuis la racine.
- Par défaut, le code utilise `http://127.0.0.1:8000` si aucune variable n'est fournie.

## 10) Déploiement sur Render.com

Voici une procédure simple pour héberger le backend sur Render (PaaS).

1) Créer le service Web

- Créez un compte sur https://render.com et connectez votre dépôt GitHub.
- New ➜ Web Service ➜ Sélectionnez le repo `LinkGuessr`.
- Name: `linkguessr-api` (au choix)
- Region: proche de vos utilisateurs
- Branch: `main`
- Environment: `Python`
- Build Command: `pip install -r backend/requirements.txt`
- Start Command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`

2) Variables d’environnement (Settings ➜ Environment)

Ajoutez les clés suivantes (ne les commitez pas):

```
NEO4J_URI=bolt://<hote_neo4j>:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<motdepasse>

# Optionnel mais recommandé si vous attachez un disque (voir ci‑dessous)
LEADERBOARD_PATH=/var/data/leaderboard.json

# Règles du leaderboard (optionnel)
LEADERBOARD_MAX_ENTRIES_PER_NAME=3
LEADERBOARD_MIN_SECONDS_BETWEEN=10
LEADERBOARD_NAME_MAX_LENGTH=16
```

Notes:
- Si vous utilisez Neo4j Aura, l’URI est souvent `neo4j+s://...` ou `bolt+s://...` (suivez la doc Aura) et ouvrez l’accès réseau.
- Si vous ne définissez pas `LEADERBOARD_PATH` et n’attachez pas de disque, le classement sera éphémère (réinitialisé lors des redeploys).

3) Disque persistant pour le classement (facultatif mais utile)

- Settings ➜ Disks ➜ Add Disk
    - Name: `data`
    - Size: `1GB` (ou plus)
    - Mount Path: `/var/data`
- Dans les variables d’environnement, définissez `LEADERBOARD_PATH=/var/data/leaderboard.json`.

4) Auto‑deploy et première mise en ligne

- Activez Auto Deploy On Push.
- Cliquez Deploy. Une URL publique sera fournie (ex: `https://linkguessr-api.onrender.com`).

5) Tests rapides

- Ouvrez `https://<votre-service>.onrender.com/leaderboard`
- Ouvrez `https://<votre-service>.onrender.com/graph`

6) CORS et frontend

Le backend permet toutes les origines (CORS) par défaut. En production, vous pouvez restreindre `allow_origins` aux domaines de votre frontend.

7) Blueprint optionnel (render.yaml)

Vous pouvez piloter Render via un `render.yaml` à la racine du repo:

```yaml
services:
    - type: web
        name: linkguessr-api
        env: python
        plan: free
        region: oregon # ou eu-central, etc.
        buildCommand: pip install -r backend/requirements.txt
        startCommand: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
        envVars:
            - key: NEO4J_URI
                sync: false
            - key: NEO4J_USER
                sync: false
            - key: NEO4J_PASSWORD
                sync: false
            - key: LEADERBOARD_PATH
                value: /var/data/leaderboard.json
            - key: LEADERBOARD_MAX_ENTRIES_PER_NAME
                value: 3
            - key: LEADERBOARD_MIN_SECONDS_BETWEEN
                value: 10
            - key: LEADERBOARD_NAME_MAX_LENGTH
                value: 16
        disk:
            name: data
            mountPath: /var/data
            sizeGB: 1
```

Commitez `render.yaml`, puis « New ➜ Blueprint » sur Render et pointez vers le repo.

---

## 11) Exécuter le script de scraping (run_test.py)

Ce script explore des pages Wikipédia pour alimenter Neo4j. Il nécessite les mêmes variables `.env` que le backend (URI, USER, PASSWORD).

Étapes:

```bash
# Depuis la racine du projet
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Vérifiez votre .env (à la racine)
# NEO4J_URI=neo4j+s://xxx.databases.neo4j.io
# NEO4J_USER=neo4j
# NEO4J_PASSWORD=...

# Lancer le scraping (exemple)
python run_test.py
```

Notes:
- Le script utilise `tqdm` pour afficher la progression si installé (sinon il s'exécute sans barre de progression).
- Les relations insérées suivent le modèle attendu par l'API: nœuds `(:Person {name})` et liens `[:CONNAIT]`.
- Les noms sont extraits proprement depuis l'URL Wikipédia (`.../wiki/Titre` ➜ `Titre`).

---

## 12) Démarrer l'ensemble du projet de A à Z (récapitulatif)

1) Cloner le dépôt et se placer à la racine
2) Créer et activer un venv
3) Installer les dépendances de la racine: `pip install -r requirements.txt`
4) Configurer `.env` (Neo4j)
5) Démarrer le backend: `uvicorn backend.main:app --reload`
6) (Optionnel) Lancer le scraping: `python run_test.py`
7) Démarrer le frontend:
    ```bash
    cd frontend
    npm install
    npm start
    ```
8) (Optionnel) Configurer l'URL API du frontend
    - `frontend/.env` ➜ `REACT_APP_API_BASE_URL=http://127.0.0.1:8000`
    - ou symlink: `ln -s ../.env frontend/.env`

Le site sera disponible sur `http://localhost:3000`, l'API sur `http://127.0.0.1:8000`.


lancer scraping :(.venv) elias@hp-info-01:~/PROJECT/LinkGuessr$ /home/elias/PROJECT/LinkGuessr/.venv/bin/python /home/elias/PROJECT/LinkGuessr/run_test.py

elias@hp-info-01:~/PROJECT/LinkGuessr$ source /home/elias/PROJECT/LinkGuessr/.venv/bin/activate
lancer backend : (.venv) elias@hp-info-01:~/PROJECT/LinkGuessr$ uvicorn backend.main:app --reload

lancer front : elias@hp-info-01:~/PROJECT/LinkGuessr/frontend$ npm start


A Faire : 
    - Rendre plus amusant le front-end
    - Affiché sous forme de graphe ? 
        - Avec tout les PCC identique
        - Avec Photo
    - Rajouter des personnes (Million)
        - Emmanuel Macron 
        - Gad Elmaleh 
        - Taylor Swift 
        - Adolf Hitler 
        - Moahmed Ali 
        - Karim Bezema 
        - Createur DBZ
        - kameto 
        - Squeezie
        
    - affiché un tableau avec les demande de chemin les plus demander

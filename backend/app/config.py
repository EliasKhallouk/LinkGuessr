import os
from pathlib import Path

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://linkguessr@localhost:5432/linkguessr")
GRAPH_FILE = Path(os.environ.get("GRAPH_FILE", "/srv/linkguessr/data/graph.npz"))
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
                if o.strip()]
# Prévisualisations Vercel (une URL par branche/déploiement), ex. https://link-guessr-git-refonte-xxx.vercel.app
CORS_ORIGIN_REGEX = os.environ.get("CORS_ORIGIN_REGEX") or None
# Jeton de la page /admin (vide = tableau de bord désactivé).
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")

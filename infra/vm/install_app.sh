#!/usr/bin/env bash
# Installe/met à jour le code de LinkGuessr sur la VM. Lancé par deploy.sh (avec sudo).
# Usage : sudo bash install_app.sh /tmp/linkguessr-app.tar.gz
# Idempotent. Ne touche qu'à /srv/linkguessr, /usr/local/bin/uv et au service linkguessr-api.
set -euo pipefail

ARCHIVE="$1"
APP_USER=linkguessr
APP_DIR=/srv/linkguessr
UV_VERSION=0.8.17

[ "$(id -u)" -eq 0 ] || { echo "À lancer avec sudo"; exit 1; }

echo "== 1. uv $UV_VERSION"
if ! /usr/local/bin/uv --version 2>/dev/null | grep -q "$UV_VERSION"; then
  tmp=$(mktemp -d)
  curl -fsSL -o "$tmp/uv.tar.gz" \
    "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-aarch64-unknown-linux-gnu.tar.gz"
  tar -xzf "$tmp/uv.tar.gz" -C "$tmp"
  install -m 755 "$tmp"/uv-aarch64-unknown-linux-gnu/uv "$tmp"/uv-aarch64-unknown-linux-gnu/uvx /usr/local/bin/
  rm -rf "$tmp"
fi

echo "== 2. Code dans $APP_DIR/app"
rm -rf "$APP_DIR/app.new"
install -d -o "$APP_USER" -g "$APP_USER" "$APP_DIR/app.new"
tar -xzf "$ARCHIVE" -C "$APP_DIR/app.new"
chown -R "$APP_USER:$APP_USER" "$APP_DIR/app.new"
# On garde les environnements Python déjà construits pour accélérer uv sync.
for d in backend pipeline; do
  [ -d "$APP_DIR/app/$d/.venv" ] && mv "$APP_DIR/app/$d/.venv" "$APP_DIR/app.new/$d/.venv"
done
rm -rf "$APP_DIR/app"
mv "$APP_DIR/app.new" "$APP_DIR/app"

echo "== 3. Environnements Python (Python géré par uv, dans $APP_DIR)"
as_app() {
  sudo -u "$APP_USER" env HOME="$APP_DIR" UV_PYTHON_INSTALL_DIR="$APP_DIR/.python" \
    UV_CACHE_DIR="$APP_DIR/.cache/uv" "$@"
}
as_app bash -c "cd $APP_DIR/app/backend && /usr/local/bin/uv sync --frozen --no-dev"
as_app bash -c "cd $APP_DIR/app/pipeline && /usr/local/bin/uv sync --frozen"

echo "== 4. Configuration"
grep -q '^GRAPH_FILE=' "$APP_DIR/.env" || echo "GRAPH_FILE=$APP_DIR/data/graph.npz" >> "$APP_DIR/.env"

echo "== 5. Service systemd linkguessr-api"
cat > /etc/systemd/system/linkguessr-api.service <<EOF
[Unit]
Description=LinkGuessr API
After=network.target postgresql.service
Requires=postgresql.service

[Service]
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR/app/backend
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/app/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --proxy-headers --no-access-log
Restart=on-failure
RestartSec=5
# Pas de journal d'accès (IP) côté API : Nginx le tient déjà, 14 jours.
# Garde-fous : la VM est partagée avec un autre projet.
MemoryMax=2G
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=$APP_DIR
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable linkguessr-api >/dev/null

if [ -f "$APP_DIR/data/graph.npz" ]; then
  systemctl restart linkguessr-api
  sleep 3
  systemctl --no-pager --lines=5 status linkguessr-api || true
else
  echo "   Pas encore de $APP_DIR/data/graph.npz : service installé mais pas démarré (lancer lg load d'abord)."
fi
echo "Terminé."

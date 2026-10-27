#!/usr/bin/env bash
# Installe Umami (mesure d'audience sans cookie) sur la VM, à côté de LinkGuessr, sans Docker.
# Usage : sudo bash install_umami.sh        (idempotent ; relancer pour mettre à jour UMAMI_VERSION)
# Ne touche qu'à /srv/umami, à la base « umami », au service umami et au bloc Nginx de linkguessr.
set -euo pipefail

UMAMI_VERSION=v3.4.0
NODE_VERSION=v24.21.0
PNPM_VERSION=12.3.4
APP_USER=umami
DIR=/srv/umami
PORT=3001
SITE=/etc/nginx/sites-available/linkguessr
WEBSITE_DOMAIN=linkguessr.com

[ "$(id -u)" -eq 0 ] || { echo "À lancer avec sudo"; exit 1; }
cd /tmp

echo "== 1. Utilisateur et dossier"
id "$APP_USER" >/dev/null 2>&1 || useradd --system --create-home --home-dir "$DIR" --shell /usr/sbin/nologin "$APP_USER"
install -d -o "$APP_USER" -g "$APP_USER" -m 750 "$DIR"

echo "== 2. Node.js $NODE_VERSION (pour Umami uniquement)"
if ! "$DIR/node/bin/node" --version 2>/dev/null | grep -q "$NODE_VERSION"; then
  tarball="node-$NODE_VERSION-linux-arm64.tar.xz"
  curl -fsSLO "https://nodejs.org/dist/$NODE_VERSION/$tarball"
  curl -fsSL "https://nodejs.org/dist/$NODE_VERSION/SHASUMS256.txt" | grep " $tarball\$" | sha256sum -c -
  rm -rf "$DIR/node" && mkdir -p "$DIR/node"
  tar -xJf "$tarball" -C "$DIR/node" --strip-components=1 && rm -f "$tarball"
  chown -R "$APP_USER:$APP_USER" "$DIR/node"
fi
as_umami() { sudo -u "$APP_USER" env HOME="$DIR" PATH="$DIR/node/bin:$PATH" COREPACK_HOME="$DIR/.corepack" "$@"; }
as_umami corepack enable --install-directory "$DIR/node/bin"
as_umami corepack prepare "pnpm@$PNPM_VERSION" --activate

echo "== 3. Base Postgres « umami »"
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='umami'" | grep -q 1; then
  DB_PASS="$(openssl rand -hex 24)"
  sudo -u postgres psql -qc "CREATE ROLE umami LOGIN PASSWORD '$DB_PASS'"
  sudo -u postgres createdb -O umami umami
  install -o "$APP_USER" -g "$APP_USER" -m 600 /dev/null "$DIR/.env"
  cat > "$DIR/.env" <<EOF
DATABASE_URL=postgresql://umami:$DB_PASS@localhost:5432/umami
APP_SECRET=$(openssl rand -hex 32)
BASE_PATH=/umami
TRACKER_SCRIPT_NAME=lg.js
DISABLE_TELEMETRY=1
DISABLE_UPDATES=1
EOF
fi

echo "== 4. Code Umami $UMAMI_VERSION et compilation (priorité basse, plusieurs minutes)"
if [ ! -f "$DIR/app/.version" ] || [ "$(cat "$DIR/app/.version")" != "$UMAMI_VERSION" ]; then
  rm -rf "$DIR/app"
  as_umami git clone --quiet --depth 1 --branch "$UMAMI_VERSION" https://github.com/umami-software/umami.git "$DIR/app"
  as_umami bash -c "cd $DIR/app && cp $DIR/.env .env && pnpm install --frozen-lockfile --silent"
  as_umami bash -c "cd $DIR/app && NODE_OPTIONS=--max-old-space-size=2048 nice -n 15 pnpm build"
  echo "$UMAMI_VERSION" > "$DIR/app/.version" && chown "$APP_USER:$APP_USER" "$DIR/app/.version"
fi

echo "== 5. Service systemd umami (127.0.0.1:$PORT)"
cat > /etc/systemd/system/umami.service <<EOF
[Unit]
Description=Umami (mesure d'audience LinkGuessr)
After=network.target postgresql.service
Requires=postgresql.service

[Service]
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$DIR/app
EnvironmentFile=$DIR/.env
Environment=PATH=$DIR/node/bin:/usr/bin:/bin
Environment=PORT=$PORT
Environment=HOSTNAME=127.0.0.1
ExecStart=$DIR/node/bin/pnpm start
Restart=on-failure
RestartSec=5
MemoryMax=700M
Nice=5
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable umami >/dev/null
systemctl restart umami

echo "== 6. Nginx : /umami/ -> Umami"
cat > /etc/nginx/snippets/linkguessr-umami.conf <<EOF
location /umami {  # sans barre finale : Umami retire lui-même la barre (sinon boucle de redirections)
    proxy_pass http://127.0.0.1:$PORT;
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
}
EOF
grep -q "linkguessr-umami.conf" "$SITE" || sed -i '0,/^\s*location \/ {/s//    include snippets\/linkguessr-umami.conf;\n\n    location \/ {/' "$SITE"
nginx -t
systemctl reload nginx

echo "== 7. Compte administrateur : mot de passe par défaut remplacé"
for i in $(seq 1 60); do curl -sf "http://127.0.0.1:$PORT/umami/api/heartbeat" >/dev/null && break; sleep 2; done
if [ ! -f /root/umami-admin-password ]; then
  ADMIN_PASS="$(openssl rand -base64 18 | tr -d '/+=')"
  TOKEN=$(curl -sf -X POST "http://127.0.0.1:$PORT/umami/api/auth/login" -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"umami"}' | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')
  if [ -n "$TOKEN" ]; then
    # Le site d'abord : changer le mot de passe invalide le jeton de connexion.
    WEBSITE=$(curl -s -X POST "http://127.0.0.1:$PORT/umami/api/websites" -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" -d "{\"name\":\"LinkGuessr\",\"domain\":\"$WEBSITE_DOMAIN\"}" || true)
    echo "   Site créé (id à mettre dans frontend/index.html) : $WEBSITE"
    curl -sf -X POST "http://127.0.0.1:$PORT/umami/api/me/password" -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" -d "{\"currentPassword\":\"umami\",\"newPassword\":\"$ADMIN_PASS\"}" >/dev/null
    install -m 600 /dev/null /root/umami-admin-password && echo "$ADMIN_PASS" > /root/umami-admin-password
  else
    echo "   ⚠️ Connexion admin impossible : changer le mot de passe à la main (admin/umami)."
  fi
fi
echo "Terminé. Mot de passe admin : sudo cat /root/umami-admin-password"

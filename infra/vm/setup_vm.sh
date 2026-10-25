#!/usr/bin/env bash
# Installation de base de LinkGuessr sur la VM Oracle (Ubuntu 22.04 ARM).
# Idempotent : peut être relancé sans risque. Ne touche pas à urban-vision.
#
# Usage :
#   scp infra/vm/setup_vm.sh ubuntu@88.96.51.44:~
#   ssh ubuntu@88.96.51.44
#   sudo DOMAIN=linkguessr.duckdns.org bash setup_vm.sh
set -euo pipefail

DOMAIN="${DOMAIN:-linkguessr.duckdns.org}"
APP_USER=linkguessr
APP_DIR=/srv/linkguessr
DB_NAME=linkguessr
DB_USER=linkguessr
PG_VERSION=17
API_PORT=8000

[ "$(id -u)" -eq 0 ] || { echo "À lancer avec sudo"; exit 1; }
cd /tmp  # évite les avertissements "could not change directory" de sudo -u postgres

echo "== 1. Swap 4 Go (la VM n'en a pas)"
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 4G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
echo 'vm.swappiness=10' > /etc/sysctl.d/99-swappiness.conf
sysctl -p /etc/sysctl.d/99-swappiness.conf >/dev/null

echo "== 2. PostgreSQL $PG_VERSION (dépôt officiel PGDG, le 14 d'Ubuntu 22.04 arrive en fin de vie)"
if ! dpkg -s "postgresql-$PG_VERSION" >/dev/null 2>&1; then
  apt-get update
  apt-get install -y curl ca-certificates lsb-release
  install -d /usr/share/postgresql-common/pgdg
  curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc https://www.postgresql.org/media/keys/ACCC4CF8.asc
  echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" \
    > /etc/apt/sources.list.d/pgdg.list
  apt-get update
  apt-get install -y "postgresql-$PG_VERSION"
fi

# Réglages pour une VM 1 cœur / 6 Go partagée avec un autre projet.
# Écoute uniquement en local : la base n'est jamais exposée sur Internet.
cat > "/etc/postgresql/$PG_VERSION/main/conf.d/linkguessr.conf" <<EOF
listen_addresses = 'localhost'
max_connections = 30
shared_buffers = 512MB
effective_cache_size = 2GB
work_mem = 16MB
maintenance_work_mem = 256MB
random_page_cost = 1.1
EOF
systemctl restart postgresql

echo "== 3. Utilisateur système et dossier $APP_DIR"
id "$APP_USER" >/dev/null 2>&1 || useradd --system --create-home --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
install -d -o "$APP_USER" -g "$APP_USER" -m 750 "$APP_DIR" "$APP_DIR/data"

echo "== 4. Base et rôle Postgres"
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
  DB_PASS="$(openssl rand -hex 24)"
  sudo -u postgres psql -qc "CREATE ROLE $DB_USER LOGIN PASSWORD '$DB_PASS'"
  install -o "$APP_USER" -g "$APP_USER" -m 600 /dev/null "$APP_DIR/.env"
  cat > "$APP_DIR/.env" <<EOF
DATABASE_URL=postgresql://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME
CORS_ORIGINS=https://linkguessr.vercel.app
EOF
  echo "   Mot de passe généré et stocké dans $APP_DIR/.env (lisible uniquement par $APP_USER)"
fi
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 \
  || sudo -u postgres createdb -O "$DB_USER" "$DB_NAME"
sudo -u postgres psql -d "$DB_NAME" -qc "CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;"

echo "== 5. Bloc Nginx pour $DOMAIN -> API 127.0.0.1:$API_PORT"
cat > /etc/nginx/sites-available/linkguessr <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;

    client_max_body_size 1m;

    location / {
        proxy_pass http://127.0.0.1:$API_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
ln -sf /etc/nginx/sites-available/linkguessr /etc/nginx/sites-enabled/linkguessr
nginx -t
systemctl reload nginx

echo "== 6. Certificat HTTPS (certbot déjà installé pour urban-vision)"
VM_IP="$(curl -s ifconfig.me)"
DNS_IP="$(getent ahostsv4 "$DOMAIN" | awk 'NR==1{print $1}')"
if [ "$VM_IP" = "$DNS_IP" ]; then
  certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --redirect
else
  echo "   $DOMAIN pointe vers '${DNS_IP:-rien}' au lieu de $VM_IP : crée/corrige le sous-domaine sur duckdns.org puis relance ce script."
fi

echo
echo "Terminé. Vérifications :"
echo "  psql :   sudo -u postgres psql -d $DB_NAME -c '\\dx'"
echo "  https :  curl -I https://$DOMAIN   (502 normal tant que l'API n'est pas déployée)"

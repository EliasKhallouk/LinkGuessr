#!/usr/bin/env bash
# Déploie le code COMMITÉ (HEAD) sur la VM, depuis le PC.
# Usage : bash infra/vm/deploy.sh [hôte ssh, défaut ek-hub]
set -euo pipefail

HOST="${1:-ek-hub}"
cd "$(git rev-parse --show-toplevel)"

archive=$(mktemp -t linkguessr-app.XXXXXX.tar.gz)
git archive --format=tar.gz -o "$archive" HEAD backend pipeline infra
echo "archive : $(git rev-parse --short HEAD), $(du -h "$archive" | cut -f1)"

scp -q "$archive" infra/vm/install_app.sh "$HOST":/tmp/
ssh "$HOST" "sudo bash /tmp/install_app.sh /tmp/$(basename "$archive") && rm -f /tmp/$(basename "$archive")"
rm -f "$archive"

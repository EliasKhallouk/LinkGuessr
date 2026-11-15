#!/usr/bin/env bash
# Rapatrie toutes les annotations de la VM (une ligne JSON par annotation) dans annotation/annotations.jsonl.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
F=pipeline/data/lab/${1:-20261001}/annotation/annotations.jsonl
ssh ek-hub 'sudo -u linkguessr bash -c "cd /srv/linkguessr/app/backend && set -a && . /srv/linkguessr/.env && set +a && .venv/bin/python -m app.annotation export"' > "$F.tmp"
mv "$F.tmp" "$F"
echo "$(wc -l < "$F") annotations -> $F"

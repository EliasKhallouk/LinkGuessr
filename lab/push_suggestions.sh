#!/usr/bin/env bash
# Envoie les propositions du modèle sur la VM (toutes : la commande est idempotente).
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
F=pipeline/data/lab/${1:-20261001}/annotation/suggestions.jsonl
scp -q "$F" ek-hub:/tmp/annot_suggestions.jsonl
ssh ek-hub 'sudo chown linkguessr /tmp/annot_suggestions.jsonl && sudo -u linkguessr bash -c "cd /srv/linkguessr/app/backend && set -a && . /srv/linkguessr/.env && set +a && .venv/bin/python -m app.annotation suggest /tmp/annot_suggestions.jsonl" && sudo rm -f /tmp/annot_suggestions.jsonl'

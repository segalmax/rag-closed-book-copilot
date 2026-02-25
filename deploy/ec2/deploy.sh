#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f ".env" ]]; then
  echo ".env missing. Copy from .env.example and set OPENAI_API_KEY."
  exit 1
fi

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "OPENAI_API_KEY is not set in shell environment."
  echo "Run: export OPENAI_API_KEY=... (or source your .env safely)."
  exit 1
fi

docker compose build app
docker compose run --rm app python ingest/preprocess_kb.py
docker compose run --rm app python ingest/embed.py
docker compose up --build -d

docker compose ps
curl -fsS http://localhost/health
echo "Deploy complete. Open http://<EC2_PUBLIC_IP>"

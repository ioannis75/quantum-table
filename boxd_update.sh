#!/usr/bin/env bash
# Update this checkout to origin/main and (re)start the server. Safe to run repeatedly. Keeps .env and local edits (stashed).
set -e
cd "$(dirname "$0")"
git fetch origin main
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "stashing local edits"; git stash push -m "boxd-$(date +%H%M%S)"; STASHED=1
fi
git checkout -B main origin/main
if [ "${STASHED:-0}" = 1 ]; then git stash pop || echo "stash left in place (conflict); see: git stash list"; fi
echo "now on $(git log -1 --format='%h %s')"
pkill -f "uvicorn app:app" 2>/dev/null && sleep 1 || true
mkdir -p data
nohup ./run.sh > data/server.log 2>&1 &
for i in $(seq 1 60); do curl -s -m 2 "localhost:${PORT:-8080}/api/health" >/dev/null && break; sleep 2; done
curl -s "localhost:${PORT:-8080}/api/health" && echo " -> http://$(hostname -I | awk '{print $1}'):${PORT:-8080}/"

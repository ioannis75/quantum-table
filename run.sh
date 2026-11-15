#!/usr/bin/env bash
# One command: creates the venv, installs, starts on 0.0.0.0:$PORT (default 8080).
set -e
cd "$(dirname "$0")"
[ -f .env ] || touch .env
set -a; . ./.env 2>/dev/null || true; set +a
PORT="${PORT:-8080}"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip -q install -r requirements.txt
# Quantum Time Gatekeeper: build ADAP's policy engine if Node 22+ and pnpm are present (otherwise built-in rules are used)
if command -v node >/dev/null && command -v pnpm >/dev/null && [ ! -f vendor/agent-delegated-authority/packages/policy-engine/dist/index.js ]; then
  mkdir -p vendor
  [ -d vendor/agent-delegated-authority ] || git clone -q --depth 1 https://github.com/Hardalion/agent-delegated-authority.git vendor/agent-delegated-authority || true
  (cd vendor/agent-delegated-authority && pnpm install --frozen-lockfile --ignore-scripts && pnpm --filter adap-policy build) || echo "ADAP build failed: using built-in rules"
fi
exec python -m uvicorn app:app --host 0.0.0.0 --port "$PORT"

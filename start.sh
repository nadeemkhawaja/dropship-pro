#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "  ◈  DropShip Pro v4.0 — eBay Developer API"
echo "  ─────────────────────────────────────────"
echo ""

# Backend
echo "▶ Installing Python deps..."
cd "$ROOT/backend"
pip install -q -r requirements.txt --break-system-packages 2>/dev/null || pip install -q -r requirements.txt

echo "▶ Starting API → http://localhost:8000"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACK=$!

# Frontend
echo "▶ Installing frontend deps..."
cd "$ROOT/frontend"
npm install --silent

echo "▶ Starting frontend → http://localhost:3000"
npm run dev &
FRONT=$!

echo ""
echo "  ✅  Open: http://localhost:3000"
echo "  📖  API docs: http://localhost:8000/docs"
echo ""
echo "  FIRST RUN: Go to Settings → eBay API and enter your keys"
echo "  Get free keys at: https://developer.ebay.com"
echo ""
echo "  Ctrl+C to stop"

trap "kill \$BACK \$FRONT 2>/dev/null; echo Stopped." EXIT
wait

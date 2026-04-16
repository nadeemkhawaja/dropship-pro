#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

# ── Detect WiFi IP ────────────────────────────────────────────
WIFI_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

echo ""
echo "  ◈  DropShip Pro v4.2 — eBay Developer API"
echo "  ─────────────────────────────────────────"
echo ""

# ── Kill anything on ports 3000 / 8000 ────────────────────────
echo "▶ Killing existing processes on ports 3000 and 8000..."
lsof -ti:3000,8000 | xargs kill -9 2>/dev/null && echo "  ✓ Cleared" || echo "  ✓ Nothing to kill"
sleep 1

# ── Backend ───────────────────────────────────────────────────
echo "▶ Installing Python deps..."
cd "$ROOT/backend"
pip install -q -r requirements.txt --break-system-packages 2>/dev/null || pip install -q -r requirements.txt

echo "▶ Starting API → http://$WIFI_IP:8000"
CORS_ORIGINS="http://localhost:3000,http://$WIFI_IP:3000,http://localhost:8000,http://$WIFI_IP:8000" \
  nohup uvicorn main:app --host 0.0.0.0 --port 8000 --reload > /tmp/dropship-backend.log 2>&1 &

# ── Frontend ──────────────────────────────────────────────────
echo "▶ Installing frontend deps..."
cd "$ROOT/frontend"
npm install --silent

echo "▶ Starting frontend → http://$WIFI_IP:3000"
nohup npm run dev > /tmp/dropship-frontend.log 2>&1 &

echo "▶ Waiting for app to start..."
sleep 4

echo ""
echo "  ✅  Running in background — opening browser..."
echo ""
echo "  🌐  Local:    http://localhost:3000"
echo "  🌐  Network:  http://$WIFI_IP:3000"
echo "  📖  API docs: http://$WIFI_IP:8000/docs"
echo "  📄  Logs:     /tmp/dropship-backend.log  /tmp/dropship-frontend.log"
echo "  🛑  Stop:     lsof -ti:3000,8000 | xargs kill -9"
echo ""

open "http://$WIFI_IP:3000"

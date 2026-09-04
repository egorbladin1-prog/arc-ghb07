#!/data/data/com.termux/files/usr/bin/bash
set -e
cd "$(dirname "$0")"

export ADMIN_ID="8233341112"
export MINIAPP_HOST="0.0.0.0"
export MINIAPP_PORT="8080"

if [ -z "${BOT_TOKEN:-}" ]; then
  if [ -f .env ]; then
    set -a
    . ./.env
    set +a
  fi
fi

if [ -z "${BOT_TOKEN:-}" ]; then
  echo "❌ BOT_TOKEN не задан."
  echo "Сделай: export BOT_TOKEN='ТОКЕН_БОТА'"
  exit 1
fi

if ! command -v python >/dev/null 2>&1; then
  pkg install python -y
fi

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "📦 Устанавливаю cloudflared..."
  pkg install cloudflared -y >/dev/null 2>&1 || true
fi

if ! command -v cloudflared >/dev/null 2>&1; then
  ARCH="$(uname -m)"
  case "$ARCH" in
    aarch64|arm64) BIN="cloudflared-linux-arm64";;
    armv7l|armv8l) BIN="cloudflared-linux-arm";;
    x86_64|amd64) BIN="cloudflared-linux-amd64";;
    i686|i386) BIN="cloudflared-linux-386";;
    *) echo "❌ Неизвестная архитектура: $ARCH"; exit 1;;
  esac
  mkdir -p "$HOME/bin"
  curl -L --fail --silent --show-error "https://github.com/cloudflare/cloudflared/releases/latest/download/$BIN" -o "$HOME/bin/cloudflared"
  chmod +x "$HOME/bin/cloudflared"
  export PATH="$HOME/bin:$PATH"
fi

if [ ! -f requirements.txt ]; then
  echo "❌ Не найден requirements.txt"
  exit 1
fi
pip install -r requirements.txt >/dev/null

rm -f tunnel.log
cloudflared tunnel --url http://127.0.0.1:8080 --no-autoupdate > tunnel.log 2>&1 &
TUNNEL_PID=$!
trap 'kill "$TUNNEL_PID" 2>/dev/null || true' EXIT

echo "🌐 Запускаю HTTPS-туннель..."
for i in $(seq 1 30); do
  URL=$(grep -oE 'https://[-a-z0-9]+\.trycloudflare\.com' tunnel.log | head -1 || true)
  [ -n "$URL" ] && break
  sleep 1
done

if [ -z "${URL:-}" ]; then
  echo "❌ Не удалось получить HTTPS URL."
  cat tunnel.log
  exit 1
fi

export MINIAPP_URL="$URL"
echo "🔥 BANNY SHOP ONLINE"
echo "🌐 Mini App: $MINIAPP_URL"
echo "👑 Admin ID: $ADMIN_ID"
echo ""
python bot.py

#!/usr/bin/env bash
set -euo pipefail

BOT_DIR=/opt/factorio-bot
FACTORIO_DIR=${FACTORIO_DIR:-/opt/factorio}
PORT=${PORT:-8080}

[ -x "$FACTORIO_DIR/bin/x64/factorio" ] || { echo "Nie widzę $FACTORIO_DIR/bin/x64/factorio"; exit 1; }
command -v python3 >/dev/null || { echo "Brak python3 — zainstaluj: apt install python3"; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' || { echo "Potrzebny Python 3.8+"; exit 1; }

RUN_USER=$(stat -c %U "$FACTORIO_DIR/saves")
echo "==> Bot będzie działał jako użytkownik: $RUN_USER (właściciel zapisów)"

mkdir -p "$BOT_DIR/data"
CFG="$BOT_DIR/server/config.json"
if [ ! -f "$CFG" ]; then
  PASS=$(python3 -c 'import secrets; print(secrets.token_urlsafe(12))')
  cat > "$CFG" <<EOF
{
  "factorio_dir": "$FACTORIO_DIR",
  "work_dir": "$BOT_DIR/data",
  "bot_mod_dir": "$BOT_DIR/mod/factorio-bot-collector",
  "interval_seconds": 300,
  "listen": "0.0.0.0",
  "port": $PORT,
  "username": "factorio",
  "password": "$PASS",
  "shadow_game_port": 34299,
  "shadow_rcon_port": 27099,
  "startup_timeout": 300
}
EOF
  echo "==> Utworzono $CFG"
fi
chown -R "$RUN_USER" "$BOT_DIR"
chmod 600 "$CFG"

echo "==> Test: jeden zrzut z kopii zapisu (może potrwać 1-3 min)..."
if [ "$RUN_USER" = "root" ]; then
  python3 "$BOT_DIR/server/app.py" --once
else
  runuser -u "$RUN_USER" -- python3 "$BOT_DIR/server/app.py" --once
fi

cat > /etc/systemd/system/factorio-bot.service <<EOF
[Unit]
Description=Factorio Bot (serwer-cien + dashboard)
After=network.target

[Service]
User=$RUN_USER
ExecStart=/usr/bin/env python3 $BOT_DIR/server/app.py
Restart=on-failure
RestartSec=10
Nice=15
IOSchedulingClass=idle

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now factorio-bot
systemctl restart factorio-bot

if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
  ufw allow "$PORT"/tcp
fi

IP=$(hostname -I | awk '{print $1}')
echo
echo "================================================"
echo " Dashboard: http://$IP:$PORT   (albo publiczne IP VPS)"
echo " Login:     $(python3 -c "import json;print(json.load(open('$CFG'))['username'])")"
echo " Hasło:     $(python3 -c "import json;print(json.load(open('$CFG'))['password'])")"
echo " Logi:      journalctl -u factorio-bot -f"
echo "================================================"

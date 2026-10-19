#!/usr/bin/env bash
set -euo pipefail

BOT_DIR=/opt/factorio-bot
FACTORIO_DIR=${FACTORIO_DIR:-/opt/factorio}
PORT=${PORT:-8080}
DOMAIN=${DOMAIN:-factorio.houseinn.org}
INTERVAL=${INTERVAL:-180}
ENABLE_RCON=${ENABLE_RCON:-0}
export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a

say() { printf '\n\033[1;33m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;31m!!  %s\033[0m\n' "$*"; }

[ -x "$FACTORIO_DIR/bin/x64/factorio" ] || { warn "Nie widzę $FACTORIO_DIR/bin/x64/factorio"; exit 1; }
command -v python3 >/dev/null || { warn "Brak python3 — zainstaluj: apt install python3"; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' || { warn "Potrzebny Python 3.8+"; exit 1; }

RUN_USER=$(stat -c %U "$FACTORIO_DIR/saves")
say "Bot będzie działał jako: $RUN_USER (właściciel zapisów)"

LIVE_PORT=""; LIVE_PASS=""
CMDLINE=$(pgrep -a -f "bin/x64/factorio.*--start-server" | grep -v factorio-bot | head -1 || true)
if [ -n "$CMDLINE" ]; then
  LIVE_PORT=$(sed -n 's/.*--rcon-port[ =]\([0-9]\+\).*/\1/p' <<<"$CMDLINE")
  [ -z "$LIVE_PORT" ] && LIVE_PORT=$(sed -n 's/.*--rcon-bind[ =][^ ]*:\([0-9]\+\).*/\1/p' <<<"$CMDLINE")
  LIVE_PASS=$(sed -n 's/.*--rcon-password[ =]\([^ ]\+\).*/\1/p' <<<"$CMDLINE")
fi
if [ -z "$LIVE_PASS" ] && [ -f "$FACTORIO_DIR/config/config.ini" ]; then
  LIVE_PASS=$(sed -n 's/^local-rcon-password=\(.*\)$/\1/p' "$FACTORIO_DIR/config/config.ini" | head -1)
  LIVE_PORT=$(sed -n 's/^local-rcon-socket=.*:\([0-9]\+\)$/\1/p' "$FACTORIO_DIR/config/config.ini" | head -1)
fi
REAL_INI="$FACTORIO_DIR/config/config.ini"
if { [ -z "$LIVE_PASS" ] || [ -z "$LIVE_PORT" ]; } && [ "$ENABLE_RCON" = 1 ]; then
  [ -f "$REAL_INI" ] || { warn "Brak $REAL_INI"; exit 1; }
  cp "$REAL_INI" "$REAL_INI.bak-factorio-bot"
  LIVE_PORT=27015
  LIVE_PASS=$(python3 -c 'import secrets; print(secrets.token_hex(16))')
  INI="$REAL_INI" LIVE_PORT="$LIVE_PORT" LIVE_PASS="$LIVE_PASS" python3 - <<'PY'
import os
p = os.environ["INI"]
lines = [l for l in open(p).read().splitlines() if not l.startswith(("local-rcon-socket=", "local-rcon-password="))]
add = ["local-rcon-socket=127.0.0.1:" + os.environ["LIVE_PORT"], "local-rcon-password=" + os.environ["LIVE_PASS"]]
if "[other]" in lines:
    i = lines.index("[other]") + 1
    lines[i:i] = add
else:
    lines += ["", "[other]"] + add
open(p, "w").write("\n".join(lines) + "\n")
PY
  say "Włączyłem RCON w $REAL_INI (tylko localhost, kopia: config.ini.bak-factorio-bot)"
  warn "ZRESTARTUJ teraz serwer Factorio, żeby RCON zadziałał. Usługa: $(systemctl list-units --type=service --all --no-legend 2>/dev/null | grep -i factorio | grep -v factorio-bot | awk '{print $1}' | head -1)"
fi
if [ -n "$LIVE_PASS" ] && [ -n "$LIVE_PORT" ]; then
  say "RCON serwera: port $LIVE_PORT — świat będzie zapisywany (/server-save) co $INTERVAL s"
else
  warn "Serwer nie ma RCON — dane będą tylko z autosave'ów (opóźnienie = interwał autosave'a)."
  warn "Włącz RCON: ENABLE_RCON=1 bash $BOT_DIR/server/install.sh  (potem restart serwera Factorio)"
  LIVE_PORT=""; LIVE_PASS=""
fi
[ -n "$CMDLINE" ] && echo "    Serwer działa jako: ${CMDLINE:0:160}"

USE_CADDY=0
if [ -n "$DOMAIN" ]; then
  if ss -ltnp 2>/dev/null | grep -E ':(80|443)\s' | grep -vq caddy; then
    warn "Port 80/443 zajmuje inny serwer WWW — pomijam Caddy, dashboard zostanie na porcie $PORT"
  else
    USE_CADDY=1
  fi
fi

mkdir -p "$BOT_DIR/data"
CFG="$BOT_DIR/server/config.json"
LISTEN=0.0.0.0
[ "$USE_CADDY" = 1 ] && LISTEN=127.0.0.1
INTERVAL="$INTERVAL" CFG="$CFG" FACTORIO_DIR="$FACTORIO_DIR" BOT_DIR="$BOT_DIR" PORT="$PORT" LISTEN="$LISTEN" \
LIVE_PORT="$LIVE_PORT" LIVE_PASS="$LIVE_PASS" python3 - <<'PY'
import json, os, secrets
p = os.environ["CFG"]
try:
    cfg = json.load(open(p))
except (OSError, ValueError):
    cfg = {"username": "factorio", "password": secrets.token_urlsafe(12)}
cfg.update({
    "factorio_dir": os.environ["FACTORIO_DIR"],
    "work_dir": os.environ["BOT_DIR"] + "/data",
    "bot_mod_dir": os.environ["BOT_DIR"] + "/mod/factorio-bot-collector",
    "interval_seconds": int(os.environ["INTERVAL"]),
    "listen": os.environ["LISTEN"],
    "port": int(os.environ["PORT"]),
    "shadow_game_port": 34299,
    "shadow_rcon_port": 27099,
    "startup_timeout": 300,
})
if os.environ["LIVE_PASS"]:
    cfg["live_rcon"] = {"host": "127.0.0.1", "port": int(os.environ["LIVE_PORT"]), "password": os.environ["LIVE_PASS"]}
else:
    cfg.pop("live_rcon", None)
json.dump(cfg, open(p, "w"), indent=2)
PY
chown -R "$RUN_USER" "$BOT_DIR/data" "$CFG"
chmod 600 "$CFG"

if [ -n "$LIVE_PASS" ]; then
  if (cd "$BOT_DIR/server" && python3 -c "
import json, rcon
c = json.load(open('config.json'))['live_rcon']
with rcon.Rcon(c['host'], c['port'], c['password'], timeout=5) as r: print('    RCON odpowiada:', r.command('/version').strip())
" 2>/dev/null); then :; else
    warn "RCON serwera nie odpowiada na porcie $LIVE_PORT — zrestartuj serwer Factorio i uruchom instalator ponownie"
  fi
fi

say "Test: jeden zrzut z kopii świata (1-3 min)..."
systemctl stop factorio-bot 2>/dev/null || true
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
systemctl enable factorio-bot >/dev/null
systemctl restart factorio-bot

if [ "$USE_CADDY" = 1 ]; then
  if ! command -v caddy >/dev/null; then
    say "Instaluję Caddy (HTTPS z Let's Encrypt)"
    if command -v apt-get >/dev/null; then
      apt-get install -y -q debian-keyring debian-archive-keyring apt-transport-https curl gnupg >/dev/null
      curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
      curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
      apt-get update >/dev/null && apt-get install -y caddy >/dev/null
    else
      warn "Brak apt-get — zainstaluj Caddy ręcznie: https://caddyserver.com/docs/install"
      USE_CADDY=0
    fi
  fi
fi

if [ "$USE_CADDY" = 1 ]; then
  CADDYFILE=/etc/caddy/Caddyfile
  BLOCK="$DOMAIN {
	reverse_proxy 127.0.0.1:$PORT
	header Strict-Transport-Security \"max-age=31536000\"
}"
  if [ -f "$CADDYFILE" ] && grep -q "^$DOMAIN" "$CADDYFILE"; then
    say "Caddyfile ma już $DOMAIN"
  elif [ ! -f "$CADDYFILE" ] || grep -q "^:80" "$CADDYFILE"; then
    printf '%s\n' "$BLOCK" > "$CADDYFILE"
  else
    printf '\n%s\n' "$BLOCK" >> "$CADDYFILE"
  fi
  systemctl enable caddy >/dev/null
  systemctl reload caddy 2>/dev/null || systemctl restart caddy

  PUB=$(curl -4 -s --max-time 5 https://api.ipify.org || true)
  DNS=$(getent ahostsv4 "$DOMAIN" | awk '{print $1; exit}' || true)
  if [ -n "$PUB" ] && [ "$PUB" != "$DNS" ]; then
    warn "DNS: $DOMAIN wskazuje na '${DNS:-nic}', a ten serwer ma IP $PUB."
    warn "Dodaj rekord A: $DOMAIN -> $PUB. Caddy pobierze certyfikat, gdy DNS zacznie działać."
  fi
  if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
    ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null
    ufw delete allow "$PORT"/tcp >/dev/null 2>&1 || true
  fi
  URL="https://$DOMAIN"
else
  if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
    ufw allow "$PORT"/tcp >/dev/null
  fi
  URL="http://$(hostname -I | awk '{print $1}'):$PORT"
fi

echo
echo "================================================"
echo " Dashboard: $URL"
echo " Login:     $(python3 -c "import json;print(json.load(open('$CFG'))['username'])")"
echo " Hasło:     $(python3 -c "import json;print(json.load(open('$CFG'))['password'])")"
echo " Zrzut:     automatycznie co $INTERVAL s, kopia świata kasowana po każdym zrzucie"
echo " Logi:      journalctl -u factorio-bot -f"
echo " Update:    git -C $BOT_DIR pull && bash $BOT_DIR/server/install.sh"
echo "================================================"

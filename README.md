# FactorioDasboard

Dashboard WWW ze statystykami fabryki Factorio 2.0 (braki, deficyty, zatory, prąd, złoża, badania, trendy 24 h) oraz bot-pomocnik dla Claude Code (serwer MCP).

## Osiągnięcia zostają włączone

Prawdziwy serwer pozostaje nietknięty: nie ma na nim modów ani komend Lua. Co kilka minut najnowszy autosave jest kopiowany i ładowany w osobnej, ukrytej instancji Factorio ("serwer-cień") z modem `factorio-bot-collector`. Mod zwraca statystyki przez RCON, a kopia jest od razu usuwana. Bot nie wykonuje niczego w grze. Pomaga w budowaniu przez blueprint stringi do wklejenia.

## Struktura

| Folder | Co robi |
|---|---|
| `mod/factorio-bot-collector` | Mod zbierający dane, ładowany tylko na kopii zapisu |
| `server/` | Usługa na VPS: serwer-cień, analiza i dashboard WWW (Python 3.8+, tylko biblioteka standardowa) |
| `mcp/` | Serwer MCP dla Claude Code, uruchamiany lokalnie |

## Instalacja na VPS (Linux, Factorio w `/opt/factorio`)

```bash
ssh root@IP_VPS "mkdir -p /opt/factorio-bot"
scp -r server mod root@IP_VPS:/opt/factorio-bot/
ssh root@IP_VPS "bash /opt/factorio-bot/server/install.sh"
```

Instalator robi testowy zrzut, zakłada usługę systemd `factorio-bot` i wypisuje adres, login oraz hasło dashboardu (domyślnie port `8080`). Logi sprawdzisz poleceniem `journalctl -u factorio-bot -f`.

## Bot w Claude Code

1. Skopiuj `mcp/config.example.json` do `mcp/config.json` i wpisz adres oraz hasło dashboardu.
2. W katalogu projektu utwórz `.mcp.json`:

```json
{
  "mcpServers": {
    "factorio": { "command": "python", "args": ["/pełna/ścieżka/do/mcp/factorio_mcp.py"] }
  }
}
```

3. Uruchom Claude Code w tym katalogu i pytaj na przykład: "czego brakuje w mojej fabryce?", "ile maszyn na 60 niebieskiej nauki/min?", "zrób blueprint linii na zielone układy".

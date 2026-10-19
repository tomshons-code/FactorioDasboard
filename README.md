# FactorioDasboard

Dashboard WWW dla serwera Factorio 2.0 i bot-pomocnik dla Claude Code (serwer MCP).

- **Przegląd**: ile maszyn pracuje, prąd, braki, badania.
- **Sugestie**: konkretne rady do istniejących budowli, np. ile maszyn albo wierteł dobudować, co ulepszyć, gdzie są puste sloty modułów, kiedy kończy się złoże.
- **Mapa**: cała fabryka (budynki, taśmy, rury, tory, ruda) z pinezkami problemów. Pinezki grupują się przy oddaleniu, po kliknięciu pokazują szczegóły i tag GPS do wklejenia na czat w grze.
- **Produkcja, energia, wydobycie, badania, trendy z 24 h.**

## Osiągnięcia zostają włączone

Na prawdziwym serwerze nie ma modów ani komend Lua. Co 5 minut bot wysyła przez RCON `/server-save` (zwykła komenda serwera, nie Lua). Świeży zapis jest kopiowany i ładowany w osobnej, ukrytej instancji Factorio ("serwer-cień") z modem `factorio-bot-collector`. Po zebraniu danych kopia jest kasowana, więc nic nie zapycha dysku. Jeśli serwer nie ma RCON, bot korzysta z autosave'ów.

## Struktura

| Folder | Co robi |
|---|---|
| `mod/factorio-bot-collector` | Mod zbierający dane i mapę, ładowany tylko na kopii zapisu |
| `server/` | Usługa na VPS: serwer-cień, analiza, sugestie i dashboard (Python 3.8+, bez zależności) |
| `mcp/` | Serwer MCP dla Claude Code, uruchamiany lokalnie |

## Instalacja na VPS

Wymagania: Linux, Factorio w `/opt/factorio` i rekord DNS typu A dla domeny wskazujący na IP serwera.

```bash
git clone https://github.com/tomshons-code/FactorioDasboard.git /opt/factorio-bot
DOMAIN=factorio.houseinn.org bash /opt/factorio-bot/server/install.sh
```

Instalator:

- wykrywa RCON serwera,
- robi testowy zrzut,
- zakłada usługę `factorio-bot`,
- instaluje Caddy z automatycznym HTTPS,
- na koniec wypisuje adres, login i hasło.

Aktualizacja:

```bash
git -C /opt/factorio-bot pull && bash /opt/factorio-bot/server/install.sh
```

Logi: `journalctl -u factorio-bot -f`

## Bot w Claude Code

1. Skopiuj `mcp/config.example.json` do `mcp/config.json` i wpisz adres (`https://factorio.houseinn.org`) oraz hasło.
2. W katalogu projektu utwórz `.mcp.json`:

```json
{
  "mcpServers": {
    "factorio": { "command": "python", "args": ["/pełna/ścieżka/do/mcp/factorio_mcp.py"] }
  }
}
```

3. Uruchom Claude Code w tym katalogu i pytaj na przykład: "czego brakuje w mojej fabryce?", "co poprawić przy hutach?", "ile maszyn na 60 niebieskiej nauki/min?", "zrób blueprint linii na zielone układy".

import base64
import json
import math
import os
import sys
import urllib.error
import urllib.request
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.environ.get("FACTORIO_MCP_CONFIG", os.path.join(HERE, "config.json"))

DEFAULT_SPEED = {
    "crafting": 0.75, "advanced-crafting": 0.75, "crafting-with-fluid": 0.75,
    "smelting": 2.0, "chemistry": 1.0, "oil-processing": 1.0, "centrifuging": 1.0,
    "rocket-building": 1.0,
}


def cfg():
    with open(CONFIG, encoding="utf-8") as fh:
        return json.load(fh)


def api(path, method="GET", data=None):
    c = cfg()
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(c["url"].rstrip("/") + path, method=method, data=body)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    token = base64.b64encode(("%s:%s" % (c["username"], c["password"])).encode()).decode()
    req.add_header("Authorization", "Basic " + token)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def latest():
    d = api("/api/latest")
    if not d.get("summary"):
        raise RuntimeError("Dashboard nie ma jeszcze danych: %s" % d.get("status"))
    return d


def t_overview(_):
    d = latest()
    return {
        "game_time": d["game_time"], "save": d.get("save"), "summary": d["summary"],
        "alerts": d["alerts"], "research": d["research"], "science": d["science"],
        "top_production": [{k: r[k] for k in ("name", "prod", "cons")} for r in d["top_production"]],
        "status": d.get("status"),
    }


def t_shortages(_):
    d = latest()
    return {"shortages": d["shortages"], "deficits": d["deficits"], "blocked": d["blocked"]}


def t_power(_):
    d = latest()
    return {"networks": d["power"], "low_power_machines": d["summary"]["low_power"]}


def t_mining(_):
    return {"sites": latest()["mining"]}


def t_research(_):
    d = latest()
    return {"research": d["research"], "science": d["science"]}


def t_lines(args):
    d = latest()
    q = (args.get("filter") or "").lower()
    lines = [l for l in d["lines"] if not q or q in l["recipe"].lower() or q in (l.get("product") or "").lower()]
    return {"lines": lines[: int(args.get("limit", 60))], "total": len(lines)}


def t_item(args):
    name = args["item"]
    d = latest()
    recipes = api("/api/recipes")
    hist = api("/api/history?item=" + urllib.request.quote(name))[-24:]
    makers = [r for r, v in recipes.items() if any(p["name"] == name for p in v["products"])]
    users = [r for r, v in recipes.items() if any(i["name"] == name for i in v["ingredients"])]
    return {
        "item": name,
        "rates_per_min": d["rates"].get(name),
        "shortage": next((s for s in d["shortages"] if s["item"] == name), None),
        "deficit": next((s for s in d["deficits"] if s["item"] == name), None),
        "lines_producing": [l for l in d["lines"] if l["recipe"] in makers],
        "lines_consuming": [l for l in d["lines"] if l["recipe"] in users],
        "recipes_producing": makers, "recipes_consuming": users[:30],
        "history_last_2h": hist,
    }


def t_recipe(args):
    recipes = api("/api/recipes")
    name = args["name"]
    if name in recipes:
        return {name: recipes[name]}
    hits = {k: v for k, v in recipes.items() if name in k or any(p["name"] == name for p in v["products"])}
    return hits or {"error": "Nie znam receptury %s (albo nie jest jeszcze odblokowana)" % name}


def _pick_recipe(item, recipes):
    if item in recipes and any(p["name"] == item for p in recipes[item]["products"]):
        return item
    cands = [k for k, v in recipes.items() if v["products"] and v["products"][0]["name"] == item]
    cands = cands or [k for k, v in recipes.items() if any(p["name"] == item for p in v["products"])]
    return sorted(cands, key=len)[0] if cands else None


def t_plan(args):
    item, rate = args["item"], float(args["per_minute"])
    speeds = dict(DEFAULT_SPEED)
    speeds.update(args.get("machine_speed") or {})
    raw_set = set(args.get("treat_as_raw") or [])
    recipes = api("/api/recipes")
    steps, raw = {}, {}

    def walk(it, need, stack):
        if it in raw_set or it in stack or len(stack) > 12:
            raw[it] = raw.get(it, 0) + need
            return
        rn = _pick_recipe(it, recipes)
        if not rn:
            raw[it] = raw.get(it, 0) + need
            return
        r = recipes[rn]
        out = next(p["amount"] for p in r["products"] if p["name"] == it)
        crafts = need / out
        sp = speeds.get(r["category"], 1.0)
        s = steps.setdefault(rn, {"recipe": rn, "category": r["category"], "crafts_per_min": 0,
                                  "machine_speed": sp, "energy": r["energy"]})
        s["crafts_per_min"] += crafts
        for ing in r["ingredients"]:
            walk(ing["name"], crafts * ing["amount"], stack | {it})

    walk(item, rate, frozenset())
    for s in steps.values():
        exact = s["crafts_per_min"] * s["energy"] / 60 / s["machine_speed"]
        s["machines_exact"] = round(exact, 2)
        s["machines"] = math.ceil(exact - 1e-9)
    return {"target": {"item": item, "per_minute": rate},
            "steps": sorted(steps.values(), key=lambda s: -s["machines_exact"]),
            "raw_per_minute": {k: round(v, 2) for k, v in raw.items()},
            "note": "Bez modułów/bonusów. Prędkości maszyn: " + json.dumps(speeds)}


def t_bp_decode(args):
    s = args["blueprint"].strip()
    data = json.loads(zlib.decompress(base64.b64decode(s[1:])).decode("utf-8"))
    return data


def t_bp_encode(args):
    obj = args["json"]
    if isinstance(obj, str):
        obj = json.loads(obj)
    bp = obj.get("blueprint")
    if bp is not None:
        bp.setdefault("item", "blueprint")
        bp.setdefault("version", 2 << 48)
        for i, e in enumerate(bp.get("entities") or [], 1):
            e.setdefault("entity_number", i)
    raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    return {"blueprint_string": "0" + base64.b64encode(zlib.compress(raw, 9)).decode()}


def t_suggestions(args):
    d = latest()
    sug = d.get("suggestions") or []
    kind = args.get("kind")
    if kind:
        sug = [x for x in sug if x["kind"] == kind or x["severity"] == kind]
    return {"suggestions": sug}


def t_problems(args):
    m = api("/api/map")
    marks = m.get("markers") or []
    x, y, r = args.get("x"), args.get("y"), float(args.get("radius", 64))
    if x is not None and y is not None:
        marks = [k for k in marks if abs(k[0] - x) <= r and abs(k[1] - y) <= r]
    groups = {}
    for k in marks:
        g = groups.setdefault((k[4], k[5]), {"status": k[4], "entity": k[5], "count": 0, "examples": []})
        g["count"] += 1
        if len(g["examples"]) < 5:
            g["examples"].append({"gps": "[gps=%d,%d,%s]" % (k[0], k[1], k[2]), "detail": k[6]})
    out = sorted(groups.values(), key=lambda g: -g["count"])
    bounds = {n: s.get("bounds") for n, s in (m.get("surfaces") or {}).items()}
    return {"total": len(marks), "groups": out[:40], "factory_bounds": bounds}


def t_plan(_):
    p = api("/api/plan")
    p["items"] = [i for i in p.get("items") or [] if i.get("coverage", 1) < 0.95]
    return p


def t_set_goal(args):
    patch = {k: args[k] for k in ("strategy", "spm", "mall", "packs", "belt") if k in args}
    api("/api/settings", method="POST", data=patch)
    return t_plan({})


def t_refresh(_):
    api("/api/refresh", method="POST")
    return {"ok": True, "info": "Zlecono zrzut. Dane będą za ~1-2 min (po nowym autosave albo wymuszone)."}


NOARGS = {"type": "object", "properties": {}}
TOOLS = [
    ("factory_overview", "Ogólny stan fabryki Factorio: czas gry, % pracujących maszyn, prąd, alerty, badania, produkcja nauki i top produkcji. Zacznij od tego.", NOARGS, t_overview),
    ("factory_shortages", "Braki składników (na co czekają maszyny + łańcuch przyczyn), deficyty (zużycie > produkcja) i zatory (pełne wyjście). Pozycje w formacie [gps=x,y,surface] — gracz może je wkleić na czat w grze.", NOARGS, t_shortages),
    ("factory_power", "Sieci elektryczne: produkcja, zużycie, akumulatory, najwięksi odbiorcy, maszyny z niedoborem prądu.", NOARGS, t_power),
    ("factory_mining", "Pola wydobywcze: wiertła, ile rudy zostało, tempo, ile czasu starczy, wyczerpane wiertła.", NOARGS, t_mining),
    ("factory_research", "Aktualne badanie, postęp, ETA, kolejka, laboratoria i ich braki, produkcja/zużycie pakietów nauki.", NOARGS, t_research),
    ("factory_lines", "Linie produkcyjne (per receptura): liczba maszyn, wykorzystanie, max vs faktyczna produkcja, problemy z pozycjami.",
     {"type": "object", "properties": {"filter": {"type": "string", "description": "fragment nazwy receptury/produktu"},
                                       "limit": {"type": "integer"}}}, t_lines),
    ("factory_item", "Wszystko o jednym przedmiocie/płynie: produkcja i zużycie na minutę, braki, linie które go robią/zużywają, trend z ostatnich 2 h.",
     {"type": "object", "properties": {"item": {"type": "string", "description": "nazwa wewnętrzna, np. iron-plate, electronic-circuit"}},
      "required": ["item"]}, t_item),
    ("get_recipe", "Receptura (składniki, produkty, czas, kategoria) spośród odblokowanych w tej grze. Można podać nazwę receptury albo produktu.",
     {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}, t_recipe),
    ("plan_production", "Kalkulator: ile maszyn każdego typu i ile surowców/min potrzeba na X sztuk/min danego przedmiotu (z odblokowanych receptur).",
     {"type": "object", "properties": {
         "item": {"type": "string"}, "per_minute": {"type": "number"},
         "machine_speed": {"type": "object", "description": "nadpisanie prędkości per kategoria, np. {\"crafting\": 1.25, \"smelting\": 2}"},
         "treat_as_raw": {"type": "array", "items": {"type": "string"}, "description": "przedmioty traktowane jako dostarczane z zewnątrz, np. [\"iron-plate\"]"}},
      "required": ["item", "per_minute"]}, t_plan),
    ("blueprint_decode", "Dekoduje blueprint string z Factorio do JSON (żeby przeanalizować/zmodyfikować układ).",
     {"type": "object", "properties": {"blueprint": {"type": "string"}}, "required": ["blueprint"]}, t_bp_decode),
    ("blueprint_encode", "Koduje JSON blueprintu ({\"blueprint\": {\"entities\": [{\"name\", \"position\": {\"x\",\"y\"}, \"direction\"?, \"recipe\"?}], \"label\"?}}) do stringa do wklejenia w grze. Kierunki w 2.0: 0=N, 4=E, 8=S, 12=W.",
     {"type": "object", "properties": {"json": {"type": "object"}}, "required": ["json"]}, t_bp_encode),
    ("factory_suggestions", "Konkretne sugestie do istniejących budowli: ile maszyn/wierteł dobudować i gdzie, nadmiary, ulepszenia maszyn, moduły, prąd, złoża, badania, duchy. Opcjonalny filtr kind: build|rebalance|upgrade|modules|power|mining|research|logistics|high.",
     {"type": "object", "properties": {"kind": {"type": "string"}}}, t_suggestions),
    ("factory_problems", "Problemy z mapy fabryki (każda maszyna, która nie pracuje) pogrupowane wg statusu i typu, z pozycjami GPS. Podaj x, y i radius, żeby zawęzić do obszaru.",
     {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "radius": {"type": "number"}}}, t_problems),
    ("factory_plan", "Plan budowy pod cel gracza (SPM = nauka/min) i wybrany styl (Main Bus / City Blocks / bez stylu, opcjonalnie Mall): kolejne kroki od surowców w górę, linie busa w taśmach, bloki hut i placówki, stan malla, proporcje maszyn między liniami, ściąga proporcji i proporcje elektrowni. Liczone z receptur i prędkości maszyn w tej grze.", NOARGS, t_plan),
    ("set_goal", "Zmienia cel i styl budowy (zapisuje na serwerze, widać też na stronie). strategy: main_bus|city_blocks|none, spm: liczba, mall: true/false, packs: 'auto' albo lista pakietów, belt: auto|transport-belt|fast-transport-belt|express-transport-belt.",
     {"type": "object", "properties": {"strategy": {"type": "string", "enum": ["main_bus", "city_blocks", "none"]},
                                       "spm": {"type": "number"}, "mall": {"type": "boolean"},
                                       "packs": {}, "belt": {"type": "string"}}}, t_set_goal),
    ("factory_refresh", "Wymusza nowy zrzut danych z gry (kopia ostatniego autosave'a).", NOARGS, t_refresh),
]
HANDLERS = {name: fn for name, _, _, fn in TOOLS}


def reply(msg_id, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": msg_id}
    if error:
        msg["error"] = error
    else:
        msg["result"] = result
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def handle(msg):
    method, mid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
    if mid is None:
        return
    if method == "initialize":
        return reply(mid, {
            "protocolVersion": params.get("protocolVersion", "2025-06-18"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "factorio-bot", "version": "0.1.0"},
            "instructions": "Pomocnik do Factorio 2.0. Dane pochodzą z kopii ostatniego autosave'a serwera (opóźnienie kilka minut). "
                            "Nie steruje grą — budowanie przez blueprint stringi do wklejenia. Odpowiadaj po polsku, podawaj [gps=...] żeby gracz mógł znaleźć miejsce.",
        })
    if method == "ping":
        return reply(mid, {})
    if method == "tools/list":
        return reply(mid, {"tools": [{"name": n, "description": d, "inputSchema": s} for n, d, s, _ in TOOLS]})
    if method == "tools/call":
        fn = HANDLERS.get(params.get("name"))
        if not fn:
            return reply(mid, error={"code": -32602, "message": "Nieznane narzędzie"})
        try:
            out = fn(params.get("arguments") or {})
            text, is_err = json.dumps(out, ensure_ascii=False, indent=1), False
        except urllib.error.HTTPError as e:
            text, is_err = "Błąd HTTP %s z dashboardu (sprawdź login/hasło w mcp/config.json)" % e.code, True
        except Exception as e:
            text, is_err = "%s: %s" % (type(e).__name__, e), True
        return reply(mid, {"content": [{"type": "text", "text": text}], "isError": is_err})
    reply(mid, error={"code": -32601, "message": "Method not found: %s" % method})


def main():
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    for line in sys.stdin:
        line = line.strip()
        if line:
            try:
                handle(json.loads(line))
            except ValueError:
                pass


if __name__ == "__main__":
    main()

import math

OK = {"working", "normal"}
BLOCKED = {"full_output", "waiting_for_space_in_destination", "full_burnt_result_output"}
DEPLETED = {"no_minable_resources"}

UPGRADES = [
    ("assembling-machine-1", "assembling-machine-2", "+50% prędkości"),
    ("assembling-machine-2", "assembling-machine-3", "+67% prędkości, 4 sloty modułów"),
    ("stone-furnace", "steel-furnace", "2× szybciej, ten sam rozmiar"),
    ("steel-furnace", "electric-furnace", "bez paliwa, 2 sloty modułów"),
    ("burner-mining-drill", "electric-mining-drill", "2× szybciej, bez paliwa, większy obszar"),
    ("burner-inserter", "inserter", "bez paliwa, szybszy"),
    ("transport-belt", "fast-transport-belt", "2× przepustowość"),
]


def _d(x):
    return x if isinstance(x, dict) else {}


def _count(status, names):
    return sum(v for k, v in _d(status).items() if k in names)


def _gps(p):
    return "[gps=%d,%d,%s]" % (p[0], p[1], p[2]) if p else None


def _first_sample(r, statuses=None):
    for st, lst in _d(r.get("samples")).items():
        if (statuses is None or st in statuses) and lst:
            return _gps(lst[0])
    return None


def _main_entity(r):
    ents = _d(r.get("entities"))
    return max(ents.items(), key=lambda kv: kv[1])[0] if ents else "maszyn"


def _fmt(v):
    return ("%.0f" % v) if v >= 10 else ("%.1f" % v)


def capacity_model(raw, rates):
    book = _d(raw.get("recipes"))
    crafters = _d(raw.get("crafters"))
    cap, demand, prod_lines, cons_lines = {}, {}, {}, {}
    for rname, r in crafters.items():
        rp = book.get(rname)
        machines = r.get("machines", 0)
        if not rp or not rp.get("energy") or not machines:
            continue
        prod_bonus = r.get("productivity", 0) / machines
        crafts = r.get("speed", 0) / rp["energy"] * 60
        for p in rp.get("products") or []:
            amount = crafts * p["amount"] * (1 + prod_bonus)
            cap[p["name"]] = cap.get(p["name"], 0) + amount
            prod_lines.setdefault(p["name"], []).append({
                "recipe": rname, "machines": machines, "max": amount, "per_machine": amount / machines,
                "entity": _main_entity(r), "gps": _first_sample(r) or None, "blocked": _count(r.get("status"), BLOCKED),
            })
        for i in rp.get("ingredients") or []:
            amount = crafts * i["amount"]
            demand[i["name"]] = demand.get(i["name"], 0) + amount
            cons_lines.setdefault(i["name"], []).append({"recipe": rname, "max": amount, "gps": _first_sample(r)})
    bonus = raw.get("mining_productivity") or 0
    for s in raw.get("mining") or []:
        res = s.get("resource")
        if not s.get("mining_time") or not s.get("drills") or res == "(wyczerpane)":
            continue
        amount = s.get("mining_speed", 0) / s["mining_time"] * 60 * (1 + bonus)
        cap[res] = cap.get(res, 0) + amount
        prod_lines.setdefault(res, []).append({
            "recipe": res, "machines": s["drills"], "max": amount, "per_machine": amount / s["drills"],
            "entity": max(_d(s.get("entities")).items(), key=lambda kv: kv[1])[0] if _d(s.get("entities")) else "wierteł",
            "gps": _gps(s.get("center")), "blocked": _count(s.get("status"), BLOCKED), "mining": True,
        })
    cur = _d(_d(raw.get("research")).get("current"))
    for ing in cur.get("ingredients") or []:
        use = rates.get(ing["name"], {}).get("cons", 0)
        demand[ing["name"]] = demand.get(ing["name"], 0) + use
        cons_lines.setdefault(ing["name"], []).append({"recipe": "laboratoria", "max": use, "gps": None})
    return cap, demand, prod_lines, cons_lines


def build(raw, a, rates):
    out = []
    book = _d(raw.get("recipes"))
    crafters = _d(raw.get("crafters"))
    counts = _d(raw.get("entity_counts"))
    shortage_items = {s["item"] for s in a.get("shortages") or []}

    def add(sev, kind, title, detail, gps=None, item=None):
        out.append({"severity": sev, "kind": kind, "title": title, "detail": detail, "gps": gps, "item": item})

    cap, demand, prod_lines, cons_lines = capacity_model(raw, rates)
    for item, need in demand.items():
        have = cap.get(item)
        if not have or need <= have * 1.05 or need - have < 0.5:
            continue
        lines = sorted(prod_lines.get(item, []), key=lambda l: -l["machines"])
        if not lines:
            continue
        main = lines[0]
        missing = need - have
        n = max(1, math.ceil(missing / main["per_machine"]))
        what = "wiertła" if main.get("mining") else "maszyny"
        consumers = ", ".join(sorted({c["recipe"] for c in cons_lines.get(item, [])})[:4])
        add("high" if item in shortage_items else "mid", "build",
            "Dobuduj ~%d× %s → %s" % (n, main["entity"], item),
            "Przy pełnej pracy %s potrzebują %s/min %s, a obecne %s (%d) dają maks. %s/min. Brakuje %s/min."
            % (consumers, _fmt(need), item, what, main["machines"], _fmt(have), _fmt(missing)),
            main["gps"] or next((c["gps"] for c in cons_lines.get(item, []) if c["gps"]), None), item)

    for item, have in cap.items():
        need = demand.get(item, 0)
        lines = prod_lines.get(item, [])
        blocked = sum(l["blocked"] for l in lines)
        machines = sum(l["machines"] for l in lines)
        if need <= 0 or have < need * 1.8 or blocked < machines * 0.5 or machines < 4:
            continue
        per = have / machines
        spare = int((have - need * 1.15) / per)
        if spare >= 2:
            add("low", "rebalance", "Nadmiar %s — zbędne maszyny: ~%d" % (item, spare),
                "Linia może dać %s/min, a zużycie przy pełnej pracy to %s/min. %d z %d maszyn stoi z pełnym wyjściem — "
                "możesz je przestawić na coś, czego brakuje." % (_fmt(have), _fmt(need), blocked, machines),
                lines[0]["gps"], item)

    for old, new, why in UPGRADES:
        n = counts.get(old, 0)
        if n >= 4 and new in book:
            add("low", "upgrade", "Ulepsz %d× %s → %s" % (n, old, new),
                "%s. Użyj planera ulepszeń (upgrade planner) — roboty zrobią to same." % why)

    mod_kinds = [m for m in ("productivity-module-3", "productivity-module-2", "productivity-module",
                             "speed-module-3", "speed-module-2", "speed-module") if m in book]
    if mod_kinds:
        empty = []
        for rname, r in crafters.items():
            slots = r.get("module_slots", 0)
            used = sum(_d(r.get("modules")).values())
            if slots - used >= 4:
                empty.append((slots - used, rname, r))
        empty.sort(key=lambda x: -x[0])
        for free, rname, r in empty[:3]:
            add("low", "modules", "Puste sloty modułów: %s (%d)" % (rname, free),
                "Masz odblokowane %s. Moduły produktywności najlepiej opłacają się na drogich półproduktach, "
                "prędkości — tam, gdzie brakuje miejsca na maszyny." % mod_kinds[0], _first_sample(r))

    for n in raw.get("power") or []:
        cap_w = n.get("capacity_w") or 0
        use = n.get("consumption_w") or 0
        if cap_w <= 0 or use <= 0:
            continue
        load = use / cap_w
        if load > 0.75:
            extra = use * 1.3 - cap_w
            engines = math.ceil(max(extra, 0) / 900e3)
            add("high" if load > 0.92 else "mid", "power",
                "Sieć #%s pracuje na %d%% mocy" % (n.get("id"), load * 100),
                "Zużycie %.1f MW przy maks. %.1f MW. Dla 30%% zapasu dołóż ok. %.1f MW (~%d silników parowych albo %d paneli z akumulatorami)."
                % (use / 1e6, cap_w / 1e6, max(extra, 0) / 1e6, engines, math.ceil(max(extra, 0) / 42e3)),
                _gps(n.get("center")))
    solar = counts.get("solar-panel", 0)
    accs = counts.get("accumulator", 0)
    if solar >= 20 and accs < solar * 0.84 * 0.8:
        add("mid", "power", "Za mało akumulatorów do paneli",
            "Masz %d paneli i %d akumulatorów. Na noc potrzeba ok. 0.84 akumulatora na panel (~%d)."
            % (solar, accs, math.ceil(solar * 0.84)))

    for s in raw.get("mining") or []:
        depl = _count(s.get("status"), DEPLETED) + (s.get("drills", 0) if s.get("resource") == "(wyczerpane)" else 0)
        if depl >= 3:
            add("mid", "mining", "Przenieś wiertła z wyczerpanego pola (%d)" % depl,
                "Stoją bez rudy. Zdekonstruuj je i postaw na nowym złożu.", _gps(s.get("center")))
    for site in a.get("mining") or []:
        left = site.get("minutes_left")
        if left is not None and left < 180 and site.get("resource") != "(wyczerpane)":
            add("high" if left < 45 else "mid", "mining",
                "Złoże %s skończy się za ~%d min" % (site["resource"], left),
                "Zostało %d rudy przy %s/min. Czas przygotować nowe pole i przeciągnąć taśmy/pociąg."
                % (site.get("remaining") or 0, _fmt(site.get("rate_per_min") or 0)), site.get("gps"), site["resource"])

    res = _d(raw.get("research"))
    if not res.get("current"):
        add("high", "research", "Nic się nie bada",
            "Laboratoria stoją. Ustaw kolejkę badań (klawisz T) — warto mieć kilka technologii w kolejce.")
    elif len(res.get("queue") or []) <= 1:
        add("low", "research", "Kolejka badań prawie pusta",
            "Po skończeniu %s laboratoria staną. Dodaj kolejne technologie do kolejki." % res["current"].get("name"))
    for pack, n in _d(_d(res.get("labs")).get("missing")).items():
        add("mid", "research", "Laboratoria czekają na %s (%d)" % (pack, n),
            "Produkcja %s: %s/min, zużycie %s/min." % (pack, _fmt(rates.get(pack, {}).get("prod", 0)),
                                                     _fmt(rates.get(pack, {}).get("cons", 0))), item=pack)

    ghosts = _d(raw.get("ghosts"))
    total = sum(ghosts.values())
    if total:
        top = ", ".join("%s ×%d" % kv for kv in sorted(ghosts.items(), key=lambda kv: -kv[1])[:5])
        robo = counts.get("roboport", 0)
        add("mid" if total > 20 else "low", "logistics", "Duchy czekające na budowę: %d" % total,
            ("Brakuje przedmiotów albo robotów: %s." % top) +
            ("" if robo else " Nie masz roboportów — postawisz je ręcznie."))

    for name, f in _d(raw.get("fuel")).items():
        nf = _count(f.get("status"), {"no_fuel"})
        if nf:
            add("high", "power", "%d× %s bez paliwa" % (nf, name),
                "Doprowadź węgiel (albo paliwo stałe) taśmą z podajnikami, inaczej spadnie produkcja prądu.",
                _first_sample(f, {"no_fuel"}))

    order = {"high": 0, "mid": 1, "low": 2}
    out.sort(key=lambda s: order[s["severity"]])
    return out[:40]

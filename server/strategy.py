import math

DEFAULTS = {"strategy": "main_bus", "mall": True, "spm": 60, "packs": "auto", "belt": "auto"}

STRATEGIES = {
    "main_bus": "Main Bus",
    "city_blocks": "City Blocks",
    "none": "Bez stylu",
}

BELTS = [
    ("express-transport-belt", 2700),
    ("fast-transport-belt", 1800),
    ("transport-belt", 900),
]

DEFAULT_SPEED = {
    "crafting": 0.5, "advanced-crafting": 0.5, "crafting-with-fluid": 0.5,
    "smelting": 1.0, "chemistry": 1.0, "oil-processing": 1.0, "centrifuging": 1.0,
    "rocket-building": 1.0,
}
CATEGORY_MACHINE = {
    "crafting": "assembling-machine", "advanced-crafting": "assembling-machine",
    "crafting-with-fluid": "assembling-machine", "smelting": "piec", "chemistry": "chemical-plant",
    "oil-processing": "oil-refinery", "centrifuging": "centrifuge", "rocket-building": "rocket-silo",
}

PREFER = {
    "petroleum-gas": ["advanced-oil-processing", "basic-oil-processing"],
    "light-oil": ["advanced-oil-processing"],
    "heavy-oil": ["advanced-oil-processing"],
    "solid-fuel": ["solid-fuel-from-light-oil", "solid-fuel-from-petroleum-gas"],
    "uranium-235": ["uranium-processing"],
    "uranium-238": ["uranium-processing"],
}
RAW = {"iron-ore", "copper-ore", "coal", "stone", "crude-oil", "water", "uranium-ore", "wood", "raw-fish"}
SKIP_PACKS = {"space-science-pack"}

BUS_ITEMS = ["iron-plate", "copper-plate", "steel-plate", "stone-brick", "electronic-circuit",
             "advanced-circuit", "plastic-bar", "processing-unit", "sulfur"]
MINED_PER_DRILL = 30.0

MALL_ITEMS = [
    "transport-belt", "underground-belt", "splitter",
    "fast-transport-belt", "fast-underground-belt", "fast-splitter",
    "inserter", "fast-inserter", "long-handed-inserter", "bulk-inserter",
    "small-electric-pole", "medium-electric-pole", "big-electric-pole", "substation",
    "pipe", "pipe-to-ground", "pump",
    "assembling-machine-1", "assembling-machine-2", "assembling-machine-3",
    "stone-furnace", "steel-furnace", "electric-furnace", "electric-mining-drill",
    "boiler", "steam-engine", "solar-panel", "accumulator", "lab",
    "wooden-chest", "iron-chest", "steel-chest", "rail", "train-stop", "rail-signal", "rail-chain-signal",
    "roboport", "construction-robot", "logistic-robot", "chemical-plant", "oil-refinery", "beacon",
]


def _d(x):
    return x if isinstance(x, dict) else {}


def _fmt(v):
    return ("%.0f" % v) if abs(v) >= 10 else ("%.1f" % v)


def _usable(name, r):
    return "barrel" not in name and r.get("energy") and r.get("products")


def _pick(item, book):
    for name in PREFER.get(item, []):
        if name in book:
            return name
    if item in book and _usable(item, book[item]) and any(p["name"] == item for p in book[item]["products"]):
        return item
    cands = [k for k, v in book.items() if _usable(k, v) and v["products"][0]["name"] == item]
    cands = cands or [k for k, v in book.items() if _usable(k, v) and any(p["name"] == item for p in v["products"])]
    return sorted(cands, key=len)[0] if cands else None


def category_speeds(raw, book):
    acc = {}
    for rname, r in _d(raw.get("crafters")).items():
        rp = book.get(rname)
        if not rp or not r.get("machines"):
            continue
        a = acc.setdefault(rp["category"], [0.0, 0])
        a[0] += r.get("speed", 0)
        a[1] += r["machines"]
    speeds = dict(DEFAULT_SPEED)
    for cat, (sp, n) in acc.items():
        if n:
            speeds[cat] = sp / n
    return speeds


def expand(targets, book, speeds):
    need, steps, tier = {}, {}, {}

    def walk(item, rate, stack):
        need[item] = need.get(item, 0) + rate
        if item in RAW or item in stack or len(stack) > 14:
            tier.setdefault(item, 0)
            return 0
        rn = _pick(item, book)
        if not rn:
            tier.setdefault(item, 0)
            return 0
        r = book[rn]
        out = next(p["amount"] for p in r["products"] if p["name"] == item) or 1
        crafts = rate / out
        s = steps.setdefault(rn, {"recipe": rn, "item": item, "category": r["category"], "crafts": 0.0,
                                  "energy": r["energy"], "speed": speeds.get(r["category"], 1.0)})
        s["crafts"] += crafts
        depth = 0
        for ing in r["ingredients"]:
            depth = max(depth, walk(ing["name"], crafts * ing["amount"], stack | {item}))
        tier[item] = max(tier.get(item, 0), depth + 1)
        return depth + 1

    for item, rate in targets.items():
        walk(item, rate, frozenset())
    for s in steps.values():
        s["machines_exact"] = s["crafts"] * s["energy"] / 60 / s["speed"]
        s["tier"] = tier.get(s["item"], 1)
    return need, steps, tier


def pick_belt(book, setting):
    if setting and setting != "auto":
        for name, cap in BELTS:
            if name == setting:
                return name, cap
    for name, cap in BELTS:
        if name in book:
            return name, cap
    return BELTS[-1]


def build_plan(raw, a, settings):
    cfg = dict(DEFAULTS)
    cfg.update({k: v for k, v in _d(settings).items() if v is not None})
    book = _d(raw.get("recipes"))
    rates = _d(a.get("rates"))
    crafters = _d(raw.get("crafters"))
    speeds = category_speeds(raw, book)
    spm = max(1.0, float(cfg.get("spm") or 60))

    unlocked_packs = sorted(n for n in book if n.endswith("-science-pack") and n not in SKIP_PACKS)
    packs = unlocked_packs if cfg["packs"] == "auto" else [p for p in cfg["packs"] if p in book]
    targets = {p: spm for p in packs}
    need, steps, tier = expand(targets, book, speeds)

    have_machines = {r: crafters[r]["machines"] for r in crafters}
    items = []
    for rn, s in steps.items():
        item = s["item"]
        actual = rates.get(item, {}).get("prod", 0)
        required = need.get(item, 0)
        machines_now = have_machines.get(rn, 0)
        machines_needed = math.ceil(s["machines_exact"] - 1e-6)
        items.append({
            "item": item, "recipe": rn, "tier": s["tier"], "category": s["category"],
            "machine": CATEGORY_MACHINE.get(s["category"], s["category"]),
            "required": required, "actual": actual,
            "coverage": (actual / required) if required else 1,
            "machines_needed": machines_needed, "machines_now": machines_now,
            "machines_missing": max(0, machines_needed - machines_now),
        })
    for item in sorted(i for i in need if i in RAW):
        required = need[item]
        actual = rates.get(item, {}).get("prod", 0)
        items.append({
            "item": item, "recipe": None, "tier": 0, "category": "mining",
            "machine": "offshore-pump" if item == "water" else ("pumpjack" if item == "crude-oil" else "electric-mining-drill"),
            "required": required, "actual": actual, "coverage": (actual / required) if required else 1,
            "machines_needed": None if item in ("water", "crude-oil") else math.ceil(required / MINED_PER_DRILL),
            "machines_now": None, "machines_missing": None,
        })
    items.sort(key=lambda x: (x["tier"], x["item"]))

    todo = [i for i in items if i["coverage"] < 0.9]
    todo.sort(key=lambda x: (x["tier"], x["coverage"]))
    steps_out = []
    for i in todo[:12]:
        if i["recipe"] is None:
            if i["item"] == "water":
                continue
            what = "pompy ropy" if i["item"] == "crude-oil" else "wierteł (~%d)" % (i["machines_needed"] or 0)
            text = "Wydobycie %s: potrzeba %s/min, masz %s/min — dołóż %s." % (
                i["item"], _fmt(i["required"]), _fmt(i["actual"]), what)
        elif i["machines_missing"]:
            text = "%s: potrzeba %s/min, masz %s/min — dobuduj %d× %s (łącznie %d)." % (
                i["item"], _fmt(i["required"]), _fmt(i["actual"]), i["machines_missing"], i["machine"], i["machines_needed"])
        else:
            text = "%s: maszyn wystarczy (%d), ale produkują %s/min z %s/min — sprawdź zasilanie składnikami." % (
                i["item"], i["machines_now"], _fmt(i["actual"]), _fmt(i["required"]))
        steps_out.append({"item": i["item"], "tier": i["tier"], "text": text})

    belt_name, belt_cap = pick_belt(book, cfg.get("belt"))
    style = {"name": STRATEGIES.get(cfg["strategy"], cfg["strategy"]), "sections": []}
    if cfg["strategy"] == "main_bus":
        style["sections"] = main_bus(need, rates, belt_name, belt_cap, steps)
    elif cfg["strategy"] == "city_blocks":
        style["sections"] = city_blocks(need, rates, belt_name, belt_cap, steps, raw)
    mall = mall_check(raw, book, crafters) if cfg.get("mall") else None

    total_now = sum(rates.get(p, {}).get("cons", 0) for p in packs)
    extras = {"ratios": ratios(raw, book), "cheatsheet": cheatsheet(book, *pick_belt(book, cfg.get("belt"))),
              "power": power_ratios(_d(raw.get("entity_counts")))}
    return {
        "settings": cfg, "strategies": STRATEGIES,
        "belts": [b for b, _ in BELTS if b in book] or ["transport-belt"],
        "unlocked_packs": unlocked_packs, "packs": packs,
        "spm_now": min((rates.get(p, {}).get("prod", 0) for p in packs), default=0),
        "science_used_now": total_now,
        "speeds": speeds, "items": items, "steps": steps_out,
        "style": style, "mall": mall, "belt": {"name": belt_name, "per_min": belt_cap},
        **extras,
    }


def main_bus(need, rates, belt_name, belt_cap, steps):
    lanes = []
    for item in BUS_ITEMS:
        req = need.get(item, 0)
        if req <= 0:
            continue
        act = rates.get(item, {}).get("prod", 0)
        lanes.append({"item": item, "required": req, "actual": act,
                      "belts_needed": req / belt_cap, "belts_now": act / belt_cap})
    total = sum(math.ceil(l["belts_needed"] - 0.05) for l in lanes)
    modules = sorted((s for s in steps.values() if s["item"].endswith("-science-pack")), key=lambda s: s["tier"])
    tips = [
        "Bus układaj w grupach po 4 taśmy z 2 kratkami przerwy — zostaw miejsce na podziemne i splittery.",
        "Kolejność od lewej: żelazo, miedź, (przerwa) stal, zielone układy, (przerwa) cegły, plastik, czerwone układy.",
        "Odbieraj z busa splitterem z priorytetem i podziemną taśmą pod pozostałymi liniami; niebieskie układy i siarkę możesz robić lokalnie.",
        "Przy %s jedna taśma niesie %d/min — gdy linia ma ponad 85%% obciążenia, dociągnij drugą." % (belt_name, belt_cap),
    ]
    return [
        {"title": "Linie na busie (%s)" % belt_name, "kind": "lanes", "rows": lanes,
         "note": "Razem ok. %d taśm na busie dla tego celu." % total},
        {"title": "Moduły nauki wzdłuż busa", "kind": "modules",
         "rows": [{"item": s["item"], "machines": math.ceil(s["machines_exact"] - 1e-6), "tier": s["tier"]} for s in modules]},
        {"title": "Zasady Main Busa", "kind": "tips", "rows": tips},
    ]


def city_blocks(need, rates, belt_name, belt_cap, steps, raw):
    plates = {"iron-plate": "iron-ore", "copper-plate": "copper-ore", "steel-plate": "iron-plate", "stone-brick": "stone"}
    smelt = []
    for plate in plates:
        req = need.get(plate, 0)
        if req <= 0:
            continue
        act = rates.get(plate, {}).get("prod", 0)
        smelt.append({"item": plate, "required": req, "actual": act,
                      "blocks_needed": math.ceil(req / belt_cap - 0.05), "blocks_now": act / belt_cap})
    ores = []
    for ore in ("iron-ore", "copper-ore", "coal", "stone", "uranium-ore"):
        req = need.get(ore, 0)
        if req <= 0:
            continue
        act = rates.get(ore, {}).get("prod", 0)
        wagons = req / 4000.0 if ore != "uranium-ore" else req / 2000.0
        ores.append({"item": ore, "required": req, "actual": act,
                     "outposts": math.ceil(req / (belt_cap * 2) - 0.05), "wagons_per_min": wagons})
    blocks = sorted(({"item": s["item"], "machines": math.ceil(s["machines_exact"] - 1e-6), "tier": s["tier"]}
                     for s in steps.values() if s["category"] not in ("smelting",) and s["machines_exact"] >= 2),
                    key=lambda x: (x["tier"], -x["machines"]))
    tips = [
        "Bloki wyrównaj do chunków (np. 96×96 lub 128×128) — tory po obwodzie, stacje wewnątrz.",
        "Jeden blok hut = jedna pełna taśma płyt (%s, %d/min) — łatwo dokładać kolejne." % (belt_name, belt_cap),
        "Pociągi 1-4 (lokomotywa + 4 wagony) i stacje nazwane wg ładunku: 'Iron Plate Drop', 'Iron Plate Pickup'.",
        "Ustaw limity pociągów na stacjach (train limit), żeby pociągi same rozdzielały się po stacjach.",
    ]
    return [
        {"title": "Bloki hut", "kind": "smelt", "rows": smelt},
        {"title": "Placówki wydobywcze", "kind": "ores", "rows": ores},
        {"title": "Bloki produkcyjne", "kind": "modules", "rows": blocks[:14]},
        {"title": "Zasady City Blocks", "kind": "tips", "rows": tips},
    ]


def mall_check(raw, book, crafters):
    ghosts = _d(raw.get("ghosts"))
    rows = []
    for item in MALL_ITEMS:
        if item not in book:
            continue
        line = crafters.get(item)
        if not line:
            state = "missing"
        else:
            st = _d(line.get("status"))
            short = sum(v for k, v in st.items() if "shortage" in k or k == "no_ingredients")
            state = "starved" if short and short >= line.get("machines", 1) else "ok"
        rows.append({"item": item, "state": state, "ghosts": ghosts.get(item, 0),
                     "missing": sorted(_d((line or {}).get("missing")).keys())})
    order = {"missing": 0, "starved": 1, "ok": 2}
    rows.sort(key=lambda r: (order[r["state"]], -r["ghosts"], r["item"]))
    done = sum(1 for r in rows if r["state"] != "missing")
    return {"rows": rows, "automated": done, "total": len(rows)}


def ratios(raw, book):
    crafters = _d(raw.get("crafters"))
    lines = {}
    for rn, r in crafters.items():
        rp = book.get(rn)
        if not rp or not r.get("machines") or not rp.get("energy"):
            continue
        per = r.get("speed", 0) / r["machines"] / rp["energy"] * 60
        prod = 1 + r.get("productivity", 0) / r["machines"]
        lines[rn] = {"machines": r["machines"], "per": per, "prod": prod, "rp": rp}
    out = []
    for b, B in lines.items():
        for ing in B["rp"]["ingredients"]:
            for a, A in lines.items():
                if a == b:
                    continue
                prod_a = next((p["amount"] for p in A["rp"]["products"] if p["name"] == ing["name"]), 0)
                if not prod_a:
                    continue
                supply = A["per"] * prod_a * A["prod"]
                demand = B["per"] * ing["amount"]
                if supply <= 0:
                    continue
                ideal_a = B["machines"] * demand / supply
                diff = A["machines"] - ideal_a
                g = _simple_ratio(demand / supply)
                out.append({
                    "producer": a, "consumer": b, "item": ing["name"],
                    "producer_machines": A["machines"], "consumer_machines": B["machines"],
                    "ideal_producer": ideal_a, "ratio": g, "balance": A["machines"] / ideal_a if ideal_a else None,
                    "missing": max(0, math.ceil(ideal_a - A["machines"] - 1e-6)),
                    "spare": max(0, int(-diff)) if diff < 0 else 0,
                })
    out.sort(key=lambda x: (x["balance"] if x["balance"] is not None else 9))
    return out[:40]


def _simple_ratio(x):
    best = (1, 1, 9)
    for den in range(1, 11):
        num = round(x * den)
        if num < 1:
            continue
        err = abs(num / den - x)
        if err < best[2] - 1e-9:
            best = (num, den, err)
        if err < 0.005 * x:
            break
    return "%d : %d" % (best[0], best[1])


def cheatsheet(book, belt_name, belt_cap):
    per_s = belt_cap / 60.0
    rows = []
    rows.append(("Wiertła elektryczne na taśmę", "%d" % round(per_s / 0.5), "0.5/s na wiertło (bez bonusów)"))
    rows.append(("Piece kamienne na taśmę płyt", "%d" % round(per_s / 0.3125), "0.3125 płyty/s na piec"))
    if "steel-furnace" in book or "electric-furnace" in book:
        rows.append(("Piece stalowe / elektryczne na taśmę", "%d" % round(per_s / 0.625), "0.625 płyty/s na piec"))
    rows.append(("Płyty żelaza → stal (piece stalowe)", "5 : 1", "5 płyt → 1 stal, 16 s"))
    rows.append(("Kabel : zielone układy", "3 : 2", "te same maszyny"))
    rows.append(("Koła zębate : czerwona nauka", "1 : 10", "asembler 0.5"))
    rows.append(("Czerwona : zielona nauka", "5 : 6", "te same maszyny"))
    rows.append(("Pompa : kotły : silniki parowe", "1 : 20 : 40", "36 MW z jednej pompy"))
    if "solar-panel" in book:
        rows.append(("Panele słoneczne : akumulatory", "25 : 21", "≈ 42 kW średnio na panel"))
        rows.append(("Panele na 1 MW całodobowo", "≈ 24 + 20 akum.", "wliczając noc"))
    if "nuclear-reactor" in book:
        rows.append(("Reaktor : wymienniki : turbiny", "1 : 4 : 7", "40 MW na reaktor, 2×2 = 480 MW z bonusem"))
    if "advanced-oil-processing" in book:
        rows.append(("Rafinerie : cracking ciężki : lekki", "≈ 20 : 5 : 17", "maks. gaz z ropy"))
    if "advanced-circuit" in book:
        rows.append(("Kabel : zielone : czerwone układy", "5 : 2 : 12", "te same maszyny, plastik dowozisz z boku"))
    rows.append(("Taśma %s" % belt_name, "%d/min" % belt_cap, "%g/s, 2 pasy po %g/s" % (per_s, per_s / 2)))
    return [{"what": a, "ratio": b, "note": c} for a, b, c in rows]


def power_ratios(counts):
    out = []
    pumps, boilers, engines = counts.get("offshore-pump", 0), counts.get("boiler", 0), counts.get("steam-engine", 0)
    if boilers or engines:
        out.append({"setup": "Para", "have": "%d pomp : %d kotłów : %d silników" % (pumps, boilers, engines),
                    "ideal": "1 : 20 : 40",
                    "ok": engines == boilers * 2 and pumps * 20 >= boilers,
                    "hint": ("Na %d kotłów potrzeba %d silników." % (boilers, boilers * 2)) if engines != boilers * 2 else
                            ("Dołóż pompę — jedna obsłuży 20 kotłów." if pumps * 20 < boilers else "Proporcja idealna.")})
    solar, acc = counts.get("solar-panel", 0), counts.get("accumulator", 0)
    if solar:
        ideal = math.ceil(solar * 21 / 25)
        out.append({"setup": "Solar", "have": "%d paneli : %d akumulatorów" % (solar, acc), "ideal": "25 : 21",
                    "ok": acc >= ideal * 0.95,
                    "hint": "Proporcja dobra." if acc >= ideal * 0.95 else "Dołóż %d akumulatorów na noc." % (ideal - acc)})
    reactors, hx, turb = counts.get("nuclear-reactor", 0), counts.get("heat-exchanger", 0), counts.get("steam-turbine", 0)
    if reactors:
        out.append({"setup": "Atom", "have": "%d reaktorów : %d wymienników : %d turbin" % (reactors, hx, turb),
                    "ideal": "1 : 4 : 7 (bez bonusu sąsiedztwa)", "ok": turb >= hx * 1.7,
                    "hint": "Na %d wymienników potrzeba ok. %d turbin." % (hx, math.ceil(hx * 1.75))})
    return out

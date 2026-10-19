import time

import suggest

OK = {"working", "normal"}
SHORTAGE = {"item_ingredient_shortage", "fluid_ingredient_shortage", "no_ingredients",
            "missing_required_fluid", "no_input_fluid"}
BLOCKED = {"full_output", "waiting_for_space_in_destination", "full_burnt_result_output"}
POWER = {"no_power", "low_power"}
DEPLETED = {"no_minable_resources"}
NO_FUEL = {"no_fuel"}

STATUS_PL = {
    "working": "pracuje", "normal": "ok", "no_ingredients": "brak składników",
    "item_ingredient_shortage": "brak składnika", "fluid_ingredient_shortage": "brak płynu",
    "missing_required_fluid": "brak płynu", "no_input_fluid": "brak płynu",
    "full_output": "pełne wyjście", "waiting_for_space_in_destination": "brak miejsca na wyjściu",
    "no_power": "brak prądu", "low_power": "słaby prąd", "no_fuel": "brak paliwa",
    "no_recipe": "brak receptury", "no_minable_resources": "złoże wyczerpane",
    "disabled_by_control_behavior": "wyłączone sygnałem", "disabled_by_script": "wyłączone skryptem",
    "marked_for_deconstruction": "do rozbiórki", "missing_science_packs": "brak pakietów",
    "no_research_in_progress": "brak badania", "waiting_for_source_items": "czeka na wsad",
    "frozen": "zamrożone", "none": "-",
}


def d(x):
    return x if isinstance(x, dict) else {}


def gps(p):
    if not p:
        return None
    return "[gps=%d,%d,%s]" % (p[0], p[1], p[2])


def fmt_time(ticks):
    s = int(ticks / 60)
    return "%dh %02dmin" % (s // 3600, (s % 3600) // 60)


def _rates(raw):
    out = {}
    prod = d(raw.get("production"))
    for kind in ("item", "fluid"):
        for name, t in d(prod.get(kind)).items():
            p, c = d(t.get("prod")), d(t.get("cons"))
            out[name] = {
                "name": name, "kind": kind,
                "prod": p.get("m10", 0), "cons": c.get("m10", 0),
                "prod_1m": p.get("m1", 0), "cons_1m": c.get("m1", 0),
                "prod_1h": p.get("h1", 0), "cons_1h": c.get("h1", 0),
                "total_prod": t.get("total_prod", 0), "total_cons": t.get("total_cons", 0),
            }
    return out


def _producers(recipes_book):
    out = {}
    for rname, r in recipes_book.items():
        for p in r.get("products") or []:
            out.setdefault(p["name"], []).append(rname)
    return out


def _samples(r, statuses):
    s = d(r.get("samples"))
    res = []
    for st in statuses:
        res.extend(s.get(st) or [])
    return res[:5]


def _count(status, names):
    return sum(v for k, v in d(status).items() if k in names)


def _cause_chain(item, crafters, producers, mining_resources, depth=0, seen=None):
    seen = seen or set()
    if item in seen or depth > 6:
        return []
    seen.add(item)
    recipes_here = [r for r in producers.get(item, []) if r in crafters]
    if not recipes_here:
        if item in mining_resources:
            return [{"item": item, "reason": "wydobycie nie nadąża / złoże"}]
        return [{"item": item, "reason": "nikt w fabryce tego nie produkuje"}]
    machines = sum(crafters[r]["machines"] for r in recipes_here)
    missing = {}
    for r in recipes_here:
        for ing, n in d(crafters[r].get("missing")).items():
            missing[ing] = missing.get(ing, 0) + n
    blocked_power = sum(_count(crafters[r].get("status"), POWER) for r in recipes_here)
    if blocked_power >= machines * 0.3:
        return [{"item": item, "reason": "maszyny bez prądu"}]
    if missing:
        top, n = max(missing.items(), key=lambda kv: kv[1])
        if n >= max(1, machines * 0.3):
            return [{"item": item, "reason": "czeka na %s (%d/%d maszyn)" % (top, n, machines)}] + \
                _cause_chain(top, crafters, producers, mining_resources, depth + 1, seen)
    return [{"item": item, "reason": "za mało maszyn (%d) — wszystkie pracują, nie nadążają" % machines}]


def analyze(raw):
    rates = _rates(raw)
    crafters = d(raw.get("crafters"))
    book = d(raw.get("recipes"))
    producers = _producers(book)
    mining = raw.get("mining") or []
    mining_resources = {s.get("resource") for s in mining}
    alerts = []

    lines = []
    total_machines = working_machines = 0
    for rname, r in crafters.items():
        st = d(r.get("status"))
        machines = r.get("machines", 0)
        working = _count(st, OK)
        total_machines += machines
        working_machines += working
        rp = book.get(rname)
        max_rate = None
        main = None
        if rp and rp.get("energy"):
            prods = rp.get("products") or []
            if prods:
                main = prods[0]["name"]
                prod_bonus = r.get("productivity", 0) / max(machines, 1)
                max_rate = r.get("speed", 0) / rp["energy"] * 60 * prods[0]["amount"] * (1 + prod_bonus)
        lines.append({
            "recipe": rname, "product": main, "machines": machines, "working": working,
            "utilization": working / machines if machines else 0,
            "max_per_min": max_rate,
            "actual_per_min": rates.get(main, {}).get("prod") if main else None,
            "status": {STATUS_PL.get(k, k): v for k, v in st.items()},
            "entities": d(r.get("entities")),
            "problems": [
                {"status": STATUS_PL.get(k, k), "gps": [gps(p) for p in v]}
                for k, v in d(r.get("samples")).items()
            ],
        })
    lines.sort(key=lambda x: (x["utilization"], -x["machines"]))

    short = {}
    for rname, r in crafters.items():
        for ing, n in d(r.get("missing")).items():
            e = short.setdefault(ing, {"item": ing, "machines": 0, "recipes": []})
            e["machines"] += n
            e["recipes"].append({"recipe": rname, "machines": n,
                                 "gps": [gps(p) for p in _samples(r, SHORTAGE)]})
    shortages = sorted(short.values(), key=lambda x: -x["machines"])
    for s in shortages:
        rt = rates.get(s["item"], {})
        s["prod"] = rt.get("prod", 0)
        s["cons"] = rt.get("cons", 0)
        s["recipes"].sort(key=lambda x: -x["machines"])
        s["cause"] = _cause_chain(s["item"], crafters, producers, mining_resources)
    for s in shortages[:5]:
        alerts.append({"level": "high" if s["machines"] >= 5 else "mid",
                       "text": "Brak %s — stoi przez to maszyn: %d. Przyczyna: %s" % (
                           s["item"], s["machines"], "%s — %s" % (s["cause"][-1]["item"], s["cause"][-1]["reason"]) if s["cause"] else "?"),
                       "gps": (s["recipes"][0]["gps"] or [None])[0]})

    deficits = []
    for name, rt in rates.items():
        diff = rt["cons"] - rt["prod"]
        if rt["cons"] > 1 and diff > max(1, rt["prod"] * 0.05):
            deficits.append({"item": name, "kind": rt["kind"], "prod": rt["prod"], "cons": rt["cons"],
                             "deficit": diff})
    deficits.sort(key=lambda x: -x["deficit"])

    blocked = []
    for rname, r in crafters.items():
        n = _count(r.get("status"), BLOCKED)
        if n and n >= r.get("machines", 0) * 0.25:
            blocked.append({"recipe": rname, "machines": n, "of": r.get("machines", 0),
                            "gps": [gps(p) for p in _samples(r, BLOCKED)]})
    blocked.sort(key=lambda x: -x["machines"])

    nets = []
    low_power = sum(_count(r.get("status"), POWER) for r in crafters.values())
    low_power += sum(_count(s.get("status"), POWER) for s in mining)
    for n in raw.get("power") or []:
        if n.get("production_w", 0) <= 0 and n.get("consumption_w", 0) <= 0 and n.get("poles", 0) < 5:
            continue
        cap = n.get("acc_capacity", 0)
        nets.append({
            "id": n.get("id"), "poles": n.get("poles"),
            "production_w": n.get("production_w", 0), "consumption_w": n.get("consumption_w", 0),
            "capacity_w": n.get("capacity_w", 0),
            "load": (n.get("consumption_w", 0) / n["capacity_w"]) if n.get("capacity_w") else None,
            "accumulators": n.get("accumulators", 0),
            "acc_charge": (n.get("acc_energy", 0) / cap) if cap else None,
            "top_consumers": sorted(d(n.get("consumers")).items(), key=lambda kv: -kv[1])[:8],
            "producers": sorted(d(n.get("producers")).items(), key=lambda kv: -kv[1]),
            "gps": gps(n.get("center")),
        })
    nets.sort(key=lambda x: -x["consumption_w"])
    if low_power:
        alerts.append({"level": "high", "text": "Maszyny bez prądu / ze słabym prądem: %d" % low_power, "gps": None})
    for name, f in d(raw.get("fuel")).items():
        nf = _count(f.get("status"), NO_FUEL)
        if nf:
            alerts.append({"level": "high", "text": "%d× %s bez paliwa" % (nf, name),
                           "gps": gps((_samples(f, NO_FUEL) or [None])[0])})

    sites = []
    depleted_total = 0
    for s in mining:
        st = d(s.get("status"))
        drills = s.get("drills", 0)
        working = _count(st, OK)
        depleted = _count(st, DEPLETED) + (drills if s.get("resource") == "(wyczerpane)" else 0)
        depleted_total += depleted
        rate = None
        left_min = None
        if s.get("mining_time") and drills:
            rate = s.get("mining_speed", 0) * (working / drills) / s["mining_time"] * 60
            if rate > 0 and not s.get("infinite") and s.get("remaining") is not None:
                left_min = s["remaining"] / rate
        sites.append({
            "resource": s.get("resource"), "drills": drills, "working": working, "depleted": depleted,
            "remaining": s.get("remaining"), "infinite": s.get("infinite", False),
            "rate_per_min": rate, "minutes_left": left_min,
            "status": {STATUS_PL.get(k, k): v for k, v in st.items()},
            "gps": gps(s.get("center")),
            "problem_gps": [gps(p) for v in d(s.get("samples")).values() for p in v][:5],
        })
    sites.sort(key=lambda x: (x["minutes_left"] is None, x["minutes_left"] or 0))
    for s in sites:
        if s["minutes_left"] is not None and s["minutes_left"] < 120:
            alerts.append({"level": "mid", "text": "Złoże %s kończy się za ~%d min (wierteł: %d)" % (
                s["resource"], s["minutes_left"], s["drills"]), "gps": s["gps"]})
    if depleted_total:
        alerts.append({"level": "low", "text": "Wiertła na wyczerpanym złożu: %d — do przeniesienia" % depleted_total,
                       "gps": None})

    res = d(raw.get("research"))
    cur = d(res.get("current"))
    labs = d(res.get("labs"))
    research = {"current": None, "queue": res.get("queue") or [], "researched": res.get("researched", 0),
                "labs": labs.get("count", 0), "labs_working": _count(labs.get("status"), OK),
                "labs_missing": d(labs.get("missing")),
                "labs_status": {STATUS_PL.get(k, k): v for k, v in d(labs.get("status")).items()},
                "labs_gps": [gps(p) for v in d(labs.get("samples")).values() for p in v][:5]}
    if cur:
        eta = None
        ings = cur.get("ingredients") or []
        if ings and cur.get("units"):
            first = ings[0]
            need = cur["units"] * (1 - cur.get("progress", 0)) * first["amount"]
            use = rates.get(first["name"], {}).get("cons", 0)
            eta = need / use if use > 0 else None
        research["current"] = {"name": cur.get("name"), "level": cur.get("level"),
                               "progress": cur.get("progress", 0), "units": cur.get("units"),
                               "ingredients": ings, "eta_min": eta}
    else:
        alerts.append({"level": "mid", "text": "Nic się nie bada — laboratoria stoją", "gps": None})
    for pack, n in research["labs_missing"].items():
        alerts.append({"level": "mid", "text": "Laboratoria bez %s: %d" % (pack, n), "gps": None})

    order = {"high": 0, "mid": 1, "low": 2}
    alerts.sort(key=lambda a: order[a["level"]])

    top = sorted(rates.values(), key=lambda r: -r["prod"])
    science = [r for r in rates.values() if r["name"].endswith("science-pack")]
    result = {
        "generated": time.time(),
        "tick": raw.get("tick", 0),
        "game_time": fmt_time(raw.get("tick", 0)),
        "game_version": raw.get("game_version"),
        "summary": {
            "machines": total_machines, "working": working_machines,
            "working_pct": working_machines / total_machines if total_machines else 0,
            "power_w": sum(n["consumption_w"] for n in nets),
            "power_prod_w": sum(n["production_w"] for n in nets),
            "low_power": low_power, "shortages": len(shortages), "deficits": len(deficits),
            "blocked": len(blocked), "depleted_drills": depleted_total,
            "capacity_w": sum(n["capacity_w"] for n in nets),
            "ghosts": sum(d(raw.get("ghosts")).values()),
            "beacons": raw.get("beacons", 0),
            "entities": sum(d(raw.get("entity_counts")).values()),
        },
        "alerts": alerts,
        "shortages": shortages,
        "deficits": deficits[:40],
        "blocked": blocked,
        "lines": lines,
        "power": nets,
        "mining": sites,
        "research": research,
        "science": sorted(science, key=lambda r: r["name"]),
        "top_production": top[:25],
        "rates": rates,
    }
    result["suggestions"] = suggest.build(raw, result, rates)
    result["summary"]["suggestions"] = len(result["suggestions"])
    return result


SEVERITY = {
    "no_power": 0, "no_fuel": 0, "item_ingredient_shortage": 1, "fluid_ingredient_shortage": 1,
    "no_ingredients": 1, "missing_required_fluid": 1, "no_input_fluid": 1, "missing_science_packs": 1,
    "low_power": 1, "no_minable_resources": 1,
}


def markers(raw):
    out = []
    for p in raw.get("problems") or []:
        x, y, surface, st, name, detail = (list(p) + [""] * 6)[:6]
        out.append([x, y, surface, SEVERITY.get(st, 2), STATUS_PL.get(st, st), name, detail])
    return out


def map_payload(raw, game_map, a):
    surfaces = {}
    for name, sm in d(game_map).items():
        sm = d(sm)
        surfaces[name] = {
            "bounds": sm.get("bounds"),
            "cats": {k: v for k, v in d(sm.get("cats")).items() if isinstance(v, list)},
            "ores": {k: v for k, v in d(sm.get("ores")).items() if isinstance(v, list)},
            "ore_cell": sm.get("ore_cell", 2),
        }
    sites = [{"resource": s.get("resource"), "bbox": s.get("bbox"), "surface": s.get("surface")}
             for s in raw.get("mining") or [] if s.get("bbox")]
    return {"generated": a["generated"], "surfaces": surfaces, "markers": markers(raw), "sites": sites}


def history_entry(a):
    return {
        "t": int(a["generated"]), "tick": a["tick"],
        "working_pct": round(a["summary"]["working_pct"], 4),
        "power": [round(a["summary"]["power_prod_w"]), round(a["summary"]["power_w"])],
        "items": {n: [round(r["prod"], 2), round(r["cons"], 2)] for n, r in a["rates"].items()},
    }

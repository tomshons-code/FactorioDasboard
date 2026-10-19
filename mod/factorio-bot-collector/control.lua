local VERSION = "0.2.0"
local MAX_SAMPLES = 5
local MAX_PROBLEMS = 4000
local SITE_CELL = 64
local ORE_CELL = 2
local MAP_MARGIN = 48

local function try(f, ...)
  local ok, a, b = pcall(f, ...)
  if ok then return a, b end
  return nil
end

local STATUS = {}
for k, v in pairs(defines.entity_status) do STATUS[v] = k end

local OK = {working = true, normal = true}
local SHORTAGE = {
  item_ingredient_shortage = true, fluid_ingredient_shortage = true, no_ingredients = true,
  missing_required_fluid = true, no_input_fluid = true,
}

local CAT = {
  ["transport-belt"] = "belt", ["underground-belt"] = "belt", splitter = "belt", ["linked-belt"] = "belt",
  loader = "belt", ["loader-1x1"] = "belt", ["lane-splitter"] = "belt",
  inserter = "inserter",
  pipe = "pipe", ["pipe-to-ground"] = "pipe", pump = "pipe", ["offshore-pump"] = "pipe", ["storage-tank"] = "pipe",
  ["electric-pole"] = "pole", ["power-switch"] = "pole", substation = "pole",
  ["assembling-machine"] = "assembler", ["rocket-silo"] = "assembler",
  furnace = "furnace",
  ["mining-drill"] = "drill",
  lab = "lab",
  beacon = "beacon",
  boiler = "power", generator = "power", ["solar-panel"] = "power", reactor = "power", ["heat-pipe"] = "power",
  ["burner-generator"] = "power", ["electric-energy-interface"] = "power", accumulator = "power",
  ["fusion-generator"] = "power", ["fusion-reactor"] = "power",
  container = "chest", ["logistic-container"] = "chest", ["infinity-container"] = "chest",
  ["straight-rail"] = "rail", ["curved-rail-a"] = "rail", ["curved-rail-b"] = "rail", ["half-diagonal-rail"] = "rail",
  ["legacy-straight-rail"] = "rail", ["legacy-curved-rail"] = "rail", ["rail-ramp"] = "rail",
  ["elevated-straight-rail"] = "rail", ["elevated-curved-rail-a"] = "rail", ["elevated-curved-rail-b"] = "rail",
  ["elevated-half-diagonal-rail"] = "rail", ["rail-support"] = "rail",
  ["train-stop"] = "rail", ["rail-signal"] = "rail", ["rail-chain-signal"] = "rail",
  locomotive = "train", ["cargo-wagon"] = "train", ["fluid-wagon"] = "train", ["artillery-wagon"] = "train",
  wall = "defense", gate = "defense", ["ammo-turret"] = "defense", ["electric-turret"] = "defense",
  ["fluid-turret"] = "defense", ["artillery-turret"] = "defense", radar = "defense",
  roboport = "logistics",
  ["entity-ghost"] = "ghost", ["tile-ghost"] = "skip",
  ["arithmetic-combinator"] = "circuit", ["decider-combinator"] = "circuit", ["constant-combinator"] = "circuit",
  ["selector-combinator"] = "circuit", lamp = "circuit", ["programmable-speaker"] = "circuit",
}
local SKIP = {
  character = true, car = true, ["spider-vehicle"] = true, ["spider-leg"] = true, ["construction-robot"] = true,
  ["logistic-robot"] = true, ["combat-robot"] = true, projectile = true, ["character-corpse"] = true,
  ["item-request-proxy"] = true, ["deconstructible-tile-proxy"] = true, ["tile-ghost"] = true,
}

local function status_of(e)
  local s = try(function() return e.status end)
  if s == nil then return "none" end
  return STATUS[s] or tostring(s)
end

local function pos(e)
  return {math.floor(e.position.x), math.floor(e.position.y), e.surface.name}
end

local function add_sample(t, key, e)
  local list = t[key]
  if not list then list = {}; t[key] = list end
  if #list < MAX_SAMPLES then list[#list + 1] = pos(e) end
end

local function inc(t, key, n)
  t[key] = (t[key] or 0) + (n or 1)
end

local function inventory_define(names)
  for _, n in ipairs(names) do
    if defines.inventory[n] then return defines.inventory[n] end
  end
end

local INV_CRAFTER = inventory_define({"crafter_input", "assembling_machine_input", "furnace_source"})
local INV_FURNACE = inventory_define({"furnace_source", "crafter_input"})
local INV_LAB = inventory_define({"lab_input"})

local function proto_name(x)
  if x == nil then return nil end
  if type(x) == "string" then return x end
  return try(function() return x.name end)
end

local function max_power_w(proto)
  local v = try(function() return proto.get_max_energy_production() end)
    or try(function() return proto.max_energy_production end)
    or try(function() return proto.max_power_output end)
  return (v or 0) * 60
end

local function production(force, surface, out)
  local P = defines.flow_precision_index
  local windows = {m1 = P.one_minute, m10 = P.ten_minutes, h1 = P.one_hour}
  local getters = {item = "get_item_production_statistics", fluid = "get_fluid_production_statistics"}
  for kind, getter in pairs(getters) do
    local stats = try(function() return force[getter](surface) end)
    if stats then
      local names = {}
      for n in pairs(stats.input_counts) do names[n] = true end
      for n in pairs(stats.output_counts) do names[n] = true end
      for n in pairs(names) do
        local t = out[kind][n]
        if not t then
          t = {prod = {m1 = 0, m10 = 0, h1 = 0}, cons = {m1 = 0, m10 = 0, h1 = 0}, total_prod = 0, total_cons = 0}
          out[kind][n] = t
        end
        for w, idx in pairs(windows) do
          t.prod[w] = t.prod[w] + (try(function()
            return stats.get_flow_count{name = n, category = "input", precision_index = idx}
          end) or 0)
          t.cons[w] = t.cons[w] + (try(function()
            return stats.get_flow_count{name = n, category = "output", precision_index = idx}
          end) or 0)
        end
        t.total_prod = t.total_prod + (stats.input_counts[n] or 0)
        t.total_cons = t.total_cons + (stats.output_counts[n] or 0)
      end
    end
  end
end

local function crafter_recipe(e)
  local recipe = try(function() return e.get_recipe() end)
  if recipe then return recipe.name end
  if e.type == "furnace" then
    local prev = try(function() return e.previous_recipe end)
    if prev then return proto_name(prev.name) end
  end
end

local function missing_ingredients(e, rname)
  local proto = prototypes.recipe[rname]
  if not proto then return {} end
  local inv_id = (e.type == "furnace") and INV_FURNACE or INV_CRAFTER
  local inv = inv_id and try(function() return e.get_inventory(inv_id) end)
  local missing = {}
  for _, ing in pairs(proto.ingredients) do
    local have
    if ing.type == "fluid" then
      have = try(function() return e.get_fluid_count(ing.name) end) or 0
    else
      have = inv and (try(function() return inv.get_item_count(ing.name) end) or 0) or 0
    end
    if have < ing.amount then missing[#missing + 1] = ing.name end
  end
  return missing
end

local function modules_of(e)
  local inv = try(function() return e.get_module_inventory() end)
  if not inv then return 0, nil end
  local slots = #inv
  local contents = try(function() return inv.get_contents() end) or {}
  return slots, contents
end

local function new_state()
  return {
    crafters = {}, sites = {}, nets = {}, net_capacity = {}, accs = {},
    labs = {count = 0, status = {}, samples = {}, missing = {}},
    fuel = {}, entity_counts = {}, ghosts = {}, problems = {}, map = {}, beacons = 0,
    bounds = nil,
  }
end

local function add_problem(S, e, st, detail)
  if #S.problems >= MAX_PROBLEMS then return end
  S.problems[#S.problems + 1] = {
    math.floor(e.position.x), math.floor(e.position.y), e.surface.name, st, e.name, detail or "",
  }
end

local function add_map(S, cat, e)
  local bb = e.bounding_box
  local x1, y1 = math.floor(bb.left_top.x), math.floor(bb.left_top.y)
  local x2, y2 = math.ceil(bb.right_bottom.x), math.ceil(bb.right_bottom.y)
  local w, h = math.max(1, x2 - x1), math.max(1, y2 - y1)
  local key = e.surface.name
  local sm = S.map[key]
  if not sm then sm = {cats = {}}; S.map[key] = sm end
  local list = sm.cats[cat]
  if not list then list = {}; sm.cats[cat] = list end
  local n = #list
  list[n + 1] = x1; list[n + 2] = y1; list[n + 3] = w; list[n + 4] = h
  local b = sm.bounds
  if not b then sm.bounds = {x1, y1, x1 + w, y1 + h}
  else
    if x1 < b[1] then b[1] = x1 end
    if y1 < b[2] then b[2] = y1 end
    if x1 + w > b[3] then b[3] = x1 + w end
    if y1 + h > b[4] then b[4] = y1 + h end
  end
end

local function visit_crafter(S, e, st)
  local rname = crafter_recipe(e) or "(brak receptury)"
  local r = S.crafters[rname]
  if not r then
    r = {machines = 0, speed = 0, productivity = 0, status = {}, samples = {}, missing = {}, entities = {},
         module_slots = 0, modules = {}}
    S.crafters[rname] = r
  end
  r.machines = r.machines + 1
  r.speed = r.speed + (try(function() return e.crafting_speed end) or 0)
  r.productivity = r.productivity + (try(function() return e.productivity_bonus end) or 0)
  inc(r.entities, e.name)
  inc(r.status, st)
  local slots, contents = modules_of(e)
  r.module_slots = r.module_slots + slots
  for _, m in pairs(contents or {}) do inc(r.modules, m.name, m.count) end
  local detail = rname
  if not OK[st] then add_sample(r.samples, st, e) end
  if SHORTAGE[st] and prototypes.recipe[rname] then
    local miss = missing_ingredients(e, rname)
    for _, ing in pairs(miss) do inc(r.missing, ing) end
    if #miss > 0 then detail = rname .. ": " .. table.concat(miss, ", ") end
  end
  if not OK[st] then add_problem(S, e, st, detail) end
end

local function visit_drill(S, e, st)
  local target = try(function() return e.mining_target end)
  local res = target and target.name or "(wyczerpane)"
  local cx, cy = math.floor(e.position.x / SITE_CELL), math.floor(e.position.y / SITE_CELL)
  local key = e.surface.name .. "|" .. res .. "|" .. cx .. "," .. cy
  local s = S.sites[key]
  if not s then
    s = {surface = e.surface.name, resource = res, drills = 0, mining_speed = 0, status = {}, samples = {},
         entities = {}, x1 = e.position.x, y1 = e.position.y, x2 = e.position.x, y2 = e.position.y}
    S.sites[key] = s
  end
  s.drills = s.drills + 1
  s.mining_speed = s.mining_speed + (try(function() return e.prototype.mining_speed end) or 0.5)
  inc(s.entities, e.name)
  inc(s.status, st)
  if not OK[st] then
    add_sample(s.samples, st, e)
    add_problem(S, e, st, res)
  end
  s.x1 = math.min(s.x1, e.position.x); s.y1 = math.min(s.y1, e.position.y)
  s.x2 = math.max(s.x2, e.position.x); s.y2 = math.max(s.y2, e.position.y)
end

local function visit_lab(S, e, st, needed)
  local L = S.labs
  L.count = L.count + 1
  inc(L.status, st)
  if OK[st] then return end
  add_sample(L.samples, st, e)
  local miss = {}
  local inv = INV_LAB and try(function() return e.get_inventory(INV_LAB) end)
  if inv then
    for _, n in ipairs(needed) do
      if (try(function() return inv.get_item_count(n) end) or 0) == 0 then
        inc(L.missing, n)
        miss[#miss + 1] = n
      end
    end
  end
  add_problem(S, e, st, table.concat(miss, ", "))
end

local function visit_pole(S, e)
  local id = try(function() return e.electric_network_id end)
  if not id then return end
  local n = S.nets[id]
  if not n then
    n = {id = id, surface = e.surface.name, poles = 0, consumption_w = 0, production_w = 0,
         consumers = {}, producers = {}, acc_energy = 0, acc_capacity = 0, accumulators = 0,
         capacity_w = 0, center = pos(e)}
    S.nets[id] = n
    local P = defines.flow_precision_index
    local stats = try(function() return e.electric_network_statistics end)
    if stats then
      for name in pairs(stats.input_counts) do
        local v = (try(function()
          return stats.get_flow_count{name = name, category = "input", precision_index = P.one_minute}
        end) or 0) * 60
        n.consumers[name] = v
        n.consumption_w = n.consumption_w + v
      end
      for name in pairs(stats.output_counts) do
        local v = (try(function()
          return stats.get_flow_count{name = name, category = "output", precision_index = P.one_minute}
        end) or 0) * 60
        n.producers[name] = v
        n.production_w = n.production_w + v
      end
    end
  end
  n.poles = n.poles + 1
end

local POWER_SOURCES = {generator = true, ["solar-panel"] = true, ["burner-generator"] = true,
                       ["fusion-generator"] = true}

local function visit_power(S, e, st)
  local id = try(function() return e.electric_network_id end)
  if e.type == "accumulator" then
    if id then
      local a = S.accs[id] or {count = 0, energy = 0, capacity = 0}
      a.count = a.count + 1
      a.energy = a.energy + (e.energy or 0)
      a.capacity = a.capacity + (try(function() return e.electric_buffer_size end) or 0)
      S.accs[id] = a
    end
    return
  end
  if POWER_SOURCES[e.type] and id then
    S.net_capacity[id] = (S.net_capacity[id] or 0) + max_power_w(e.prototype)
  end
  if e.type == "boiler" or e.type == "burner-generator" or e.type == "reactor" then
    local r = S.fuel[e.name]
    if not r then r = {count = 0, status = {}, samples = {}}; S.fuel[e.name] = r end
    r.count = r.count + 1
    inc(r.status, st)
    if not OK[st] then
      add_sample(r.samples, st, e)
      add_problem(S, e, st, "")
    end
  end
end

local function scan(force, surface, S, needed)
  for _, e in pairs(surface.find_entities_filtered{force = force}) do
    local t = e.type
    if not SKIP[t] then
      local cat = CAT[t] or "other"
      inc(S.entity_counts, e.name)
      if cat == "ghost" then
        local gname = try(function() return e.ghost_name end) or "?"
        inc(S.ghosts, gname)
      end
      add_map(S, cat, e)
      if cat == "assembler" and t ~= "beacon" then
        visit_crafter(S, e, status_of(e))
      elseif cat == "furnace" then
        visit_crafter(S, e, status_of(e))
      elseif cat == "drill" then
        visit_drill(S, e, status_of(e))
      elseif cat == "lab" then
        visit_lab(S, e, status_of(e), needed)
      elseif cat == "pole" and t == "electric-pole" then
        visit_pole(S, e)
      elseif cat == "power" then
        visit_power(S, e, status_of(e))
      elseif cat == "beacon" then
        S.beacons = S.beacons + 1
      elseif cat == "inserter" then
        local st = status_of(e)
        if st == "no_power" then add_problem(S, e, st, "") end
      end
    end
  end
end

local function finish_sites(S)
  local bonus = 0
  local out = {}
  for _, s in pairs(S.sites) do
    local rp = prototypes.entity[s.resource]
    if rp then
      s.infinite = rp.infinite_resource or false
      s.mining_time = try(function() return rp.mineable_properties.mining_time end) or 1
      local surface = game.surfaces[s.surface]
      local remaining, tiles = 0, 0
      local area = {{s.x1 - 3, s.y1 - 3}, {s.x2 + 3, s.y2 + 3}}
      for _, r in pairs(surface.find_entities_filtered{area = area, name = s.resource}) do
        remaining = remaining + r.amount
        tiles = tiles + 1
      end
      s.remaining = remaining
      s.tiles = tiles
    end
    s.center = {math.floor((s.x1 + s.x2) / 2), math.floor((s.y1 + s.y2) / 2), s.surface}
    s.bbox = {math.floor(s.x1), math.floor(s.y1), math.ceil(s.x2), math.ceil(s.y2)}
    s.x1, s.y1, s.x2, s.y2 = nil, nil, nil, nil
    s.productivity_bonus = bonus
    out[#out + 1] = s
  end
  return out
end

local function finish_power(S)
  local out = {}
  for id, n in pairs(S.nets) do
    local a = S.accs[id]
    if a then
      n.accumulators, n.acc_energy, n.acc_capacity = a.count, a.energy, a.capacity
    end
    n.capacity_w = S.net_capacity[id] or 0
    out[#out + 1] = n
  end
  return out
end

local function ores(S)
  for sname, sm in pairs(S.map) do
    local b = sm.bounds
    if b then
      local surface = game.surfaces[sname]
      local area = {{b[1] - MAP_MARGIN, b[2] - MAP_MARGIN}, {b[3] + MAP_MARGIN, b[4] + MAP_MARGIN}}
      local seen, ore = {}, {}
      for _, r in pairs(surface.find_entities_filtered{area = area, type = "resource"}) do
        local cx, cy = math.floor(r.position.x / ORE_CELL), math.floor(r.position.y / ORE_CELL)
        local name = r.name
        local s = seen[name]
        if not s then s = {}; seen[name] = s; ore[name] = {} end
        local k = cx * 65536 + cy
        if not s[k] then
          s[k] = true
          local l = ore[name]
          l[#l + 1] = cx * ORE_CELL
          l[#l + 1] = cy * ORE_CELL
        end
      end
      sm.ores = ore
      sm.ore_cell = ORE_CELL
    end
  end
end

local function research_info(force)
  local out = {queue = {}}
  local needed = {}
  local tech = force.current_research
  if tech then
    out.current = {
      name = tech.name, level = tech.level, progress = force.research_progress,
      units = try(function() return tech.research_unit_count end),
      unit_time = try(function() return tech.research_unit_energy / 60 end),
      ingredients = {},
    }
    for _, ing in pairs(tech.research_unit_ingredients) do
      out.current.ingredients[#out.current.ingredients + 1] = {name = ing.name, amount = ing.amount}
      needed[#needed + 1] = ing.name
    end
  end
  for _, t in pairs(try(function() return force.research_queue end) or {}) do
    out.queue[#out.queue + 1] = proto_name(t)
  end
  out.researched = 0
  for _, t in pairs(force.technologies) do
    if t.researched then out.researched = out.researched + 1 end
  end
  return out, needed
end

local function recipe_book(force)
  local out = {}
  for name, r in pairs(force.recipes) do
    if r.enabled and not r.hidden then
      local ings, prods = {}, {}
      for _, i in pairs(r.ingredients) do ings[#ings + 1] = {name = i.name, type = i.type, amount = i.amount} end
      for _, p in pairs(r.products) do
        local amount = p.amount or (((p.amount_min or 0) + (p.amount_max or 0)) / 2)
        prods[#prods + 1] = {name = p.name, type = p.type, amount = amount * (p.probability or 1)}
      end
      out[name] = {category = r.category, energy = r.energy, ingredients = ings, products = prods}
    end
  end
  return out
end

local function collect()
  local force = game.forces["player"]
  local S = new_state()
  local research, needed = research_info(force)
  local prod = {item = {}, fluid = {}}
  local surfaces = {}
  for name, surface in pairs(game.surfaces) do
    surfaces[#surfaces + 1] = name
    production(force, surface, prod)
    scan(force, surface, S, needed)
  end
  ores(S)
  research.labs = S.labs
  local stats = {
    collector = VERSION,
    tick = game.tick,
    game_version = script.active_mods["base"],
    mods = script.active_mods,
    surfaces = surfaces,
    production = prod,
    crafters = S.crafters,
    mining = finish_sites(S),
    research = research,
    power = finish_power(S),
    fuel = S.fuel,
    recipes = recipe_book(force),
    entity_counts = S.entity_counts,
    ghosts = S.ghosts,
    beacons = S.beacons,
    mining_productivity = force.mining_drill_productivity_bonus or 0,
    problems = S.problems,
  }
  return stats, S.map
end

commands.add_command("fb_collect", "Factorio Bot", function()
  local to_json = (helpers and helpers.table_to_json) or game.table_to_json
  local ok, stats, map = pcall(collect)
  if not ok then
    rcon.print(to_json({error = tostring(stats)}))
    return
  end
  local wrote = try(function()
    helpers.write_file("factorio-bot/stats.json", to_json(stats), false, 0)
    helpers.write_file("factorio-bot/map.json", to_json(map), false, 0)
    return true
  end)
  if wrote then
    rcon.print(to_json({ok = true, files = true}))
  else
    stats.map = map
    rcon.print(to_json(stats))
  end
end)

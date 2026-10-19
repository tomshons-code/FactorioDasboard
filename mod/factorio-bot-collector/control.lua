local MAX_SAMPLES = 5
local SITE_CELL = 64

local function try(f, ...)
  local ok, a, b = pcall(f, ...)
  if ok then return a, b end
  return nil
end

local STATUS = {}
for k, v in pairs(defines.entity_status) do STATUS[v] = k end

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

local function production(force)
  local P = defines.flow_precision_index
  local windows = {m1 = P.one_minute, m10 = P.ten_minutes, h1 = P.one_hour}
  local out = {item = {}, fluid = {}}
  local getters = {item = "get_item_production_statistics", fluid = "get_fluid_production_statistics"}
  for _, surface in pairs(game.surfaces) do
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
  return out
end

local SHORTAGE = {
  item_ingredient_shortage = true, fluid_ingredient_shortage = true, no_ingredients = true,
  missing_required_fluid = true, no_input_fluid = true,
}
local OK_STATUS = {working = true, normal = true}

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

local function crafters(force)
  local recipes = {}
  for _, surface in pairs(game.surfaces) do
    local list = surface.find_entities_filtered{force = force, type = {"assembling-machine", "furnace", "rocket-silo"}}
    for _, e in pairs(list) do
      local rname = crafter_recipe(e) or "(brak receptury)"
      local r = recipes[rname]
      if not r then
        r = {machines = 0, speed = 0, productivity = 0, status = {}, samples = {}, missing = {}, entities = {}}
        recipes[rname] = r
      end
      r.machines = r.machines + 1
      r.speed = r.speed + (try(function() return e.crafting_speed end) or 0)
      r.productivity = r.productivity + (try(function() return e.productivity_bonus end) or 0)
      inc(r.entities, e.name)
      local st = status_of(e)
      inc(r.status, st)
      if not OK_STATUS[st] then add_sample(r.samples, st, e) end
      if SHORTAGE[st] and prototypes.recipe[rname] then
        for _, ing in pairs(missing_ingredients(e, rname)) do inc(r.missing, ing) end
      end
    end
  end
  return recipes
end

local function drills(force)
  local sites = {}
  local bonus = force.mining_drill_productivity_bonus or 0
  for _, surface in pairs(game.surfaces) do
    for _, e in pairs(surface.find_entities_filtered{force = force, type = "mining-drill"}) do
      local target = try(function() return e.mining_target end)
      local res = target and target.name or "(wyczerpane)"
      local cx, cy = math.floor(e.position.x / SITE_CELL), math.floor(e.position.y / SITE_CELL)
      local key = surface.name .. "|" .. res .. "|" .. cx .. "," .. cy
      local s = sites[key]
      if not s then
        s = {surface = surface.name, resource = res, drills = 0, mining_speed = 0, status = {}, samples = {},
             x1 = e.position.x, y1 = e.position.y, x2 = e.position.x, y2 = e.position.y}
        sites[key] = s
      end
      s.drills = s.drills + 1
      s.mining_speed = s.mining_speed + (try(function() return e.prototype.mining_speed end) or 0.5)
      local st = status_of(e)
      inc(s.status, st)
      if not OK_STATUS[st] then add_sample(s.samples, st, e) end
      s.x1 = math.min(s.x1, e.position.x); s.y1 = math.min(s.y1, e.position.y)
      s.x2 = math.max(s.x2, e.position.x); s.y2 = math.max(s.y2, e.position.y)
    end
  end

  local out = {}
  for _, s in pairs(sites) do
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
    s.x1, s.y1, s.x2, s.y2 = nil, nil, nil, nil
    s.productivity_bonus = bonus
    out[#out + 1] = s
  end
  return out
end

local function research(force)
  local out = {queue = {}, labs = {count = 0, status = {}, samples = {}, missing = {}}}
  local tech = force.current_research
  local needed = {}
  if tech then
    out.current = {
      name = tech.name,
      level = tech.level,
      progress = force.research_progress,
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
  for _, surface in pairs(game.surfaces) do
    for _, e in pairs(surface.find_entities_filtered{force = force, type = "lab"}) do
      out.labs.count = out.labs.count + 1
      local st = status_of(e)
      inc(out.labs.status, st)
      if not OK_STATUS[st] then
        add_sample(out.labs.samples, st, e)
        local inv = INV_LAB and try(function() return e.get_inventory(INV_LAB) end)
        if inv then
          for _, n in ipairs(needed) do
            if (try(function() return inv.get_item_count(n) end) or 0) == 0 then inc(out.labs.missing, n) end
          end
        end
      end
    end
  end
  out.researched = 0
  for _, t in pairs(force.technologies) do
    if t.researched then out.researched = out.researched + 1 end
  end
  return out
end

local function power(force)
  local nets = {}
  local P = defines.flow_precision_index
  for _, surface in pairs(game.surfaces) do
    for _, pole in pairs(surface.find_entities_filtered{force = force, type = "electric-pole"}) do
      local id = try(function() return pole.electric_network_id end)
      if id then
        local n = nets[id]
        if not n then
          n = {id = id, surface = surface.name, poles = 0, consumption_w = 0, production_w = 0,
               consumers = {}, producers = {}, acc_energy = 0, acc_capacity = 0, accumulators = 0,
               center = pos(pole)}
          nets[id] = n
          local stats = try(function() return pole.electric_network_statistics end)
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
    end
    for _, acc in pairs(surface.find_entities_filtered{force = force, type = "accumulator"}) do
      local id = try(function() return acc.electric_network_id end)
      local n = id and nets[id]
      if n then
        n.accumulators = n.accumulators + 1
        n.acc_energy = n.acc_energy + (acc.energy or 0)
        n.acc_capacity = n.acc_capacity + (try(function() return acc.electric_buffer_size end) or 0)
      end
    end
  end
  local out = {}
  for _, n in pairs(nets) do out[#out + 1] = n end
  return out
end

local function fuel(force)
  local out = {}
  for _, surface in pairs(game.surfaces) do
    local list = surface.find_entities_filtered{force = force, type = {"boiler", "burner-generator", "reactor"}}
    for _, e in pairs(list) do
      local r = out[e.name]
      if not r then r = {count = 0, status = {}, samples = {}}; out[e.name] = r end
      r.count = r.count + 1
      local st = status_of(e)
      inc(r.status, st)
      if not OK_STATUS[st] then add_sample(r.samples, st, e) end
    end
  end
  return out
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
  return {
    collector = "0.1.0",
    tick = game.tick,
    game_version = script.active_mods["base"],
    mods = script.active_mods,
    surfaces = (function()
      local s = {}
      for name in pairs(game.surfaces) do s[#s + 1] = name end
      return s
    end)(),
    production = production(force),
    crafters = crafters(force),
    mining = drills(force),
    research = research(force),
    power = power(force),
    fuel = fuel(force),
    recipes = recipe_book(force),
  }
end

commands.add_command("fb_collect", "Factorio Bot: zrzut statystyk jako JSON", function()
  local ok, data = pcall(collect)
  local to_json = (helpers and helpers.table_to_json) or game.table_to_json
  if ok then
    rcon.print(to_json(data))
  else
    rcon.print(to_json({error = tostring(data)}))
  end
end)

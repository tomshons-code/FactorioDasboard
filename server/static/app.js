"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const BASE = location.origin + location.pathname.replace(/[^/]*$/, "");
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));

const IC = {
  overview: '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
  suggestions: '<path d="M9.5 2.5 11 7l4.5 1.5L11 10l-1.5 4.5L8 10 3.5 8.5 8 7z"/><path d="M18 13l.9 2.6 2.6.9-2.6.9L18 20l-.9-2.6-2.6-.9 2.6-.9z"/>',
  map: '<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2z"/><path d="M9 4v14M15 6v14"/>',
  production: '<path d="M3 21V10l5 3V10l5 3V6l5 3v12z"/><path d="M7 17h2M12 17h2M17 17h1"/>',
  power: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
  mining: '<path d="M14.5 4.5c3 0 5.5 1 6.5 2.5-2-.5-4.5-.5-6.5.5"/><path d="M14.5 4.5c0 3-1 5.5-2.5 6.5.5-2 .5-4.5-.5-6.5"/><path d="m12 12-9 9"/>',
  research: '<path d="M9 3h6M10 3v6L4.5 18.5A2 2 0 0 0 6.2 21h11.6a2 2 0 0 0 1.7-2.5L14 9V3"/><path d="M7 15h10"/>',
  trends: '<path d="M3 3v18h18"/><path d="m7 15 4-4 3 3 6-6"/>',
  refresh: '<path d="M21 12a9 9 0 1 1-2.6-6.4L21 8"/><path d="M21 3v5h-5"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
  pin: '<path d="M12 22s7-6.2 7-12a7 7 0 0 0-14 0c0 5.8 7 12 7 12z"/><circle cx="12" cy="10" r="2.5"/>',
  alert: '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
  build: '<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.6 2.6-2.4-.6-.6-2.4z"/>',
  up: '<path d="M12 19V5M5 12l7-7 7 7"/>',
  copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  minus: '<path d="M5 12h14"/>',
  target: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>',
  list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  cpu: '<rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
  box: '<path d="M21 8 12 3 3 8v8l9 5 9-5z"/><path d="m3 8 9 5 9-5M12 13v8"/>',
  ghost: '<path d="M5 21V10a7 7 0 0 1 14 0v11l-2.5-2-2.5 2-2-2-2 2-2.5-2z"/><path d="M9 10h.01M15 10h.01"/>',
  modules: '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M9 4v16M15 4v16"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
};
const svg = (name, cls = "") => `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${IC[name] || ""}</svg>`;

const VIEWS = [
  ["overview", "Przegląd", "overview"],
  ["suggestions", "Sugestie", "suggestions"],
  ["map", "Mapa", "map"],
  ["production", "Produkcja", "production"],
  ["power", "Energia", "power"],
  ["mining", "Wydobycie", "mining"],
  ["research", "Badania", "research"],
  ["trends", "Trendy", "trends"],
];

const S = {data: null, map: null, status: null, view: "overview", rendered: {}, mapLoaded: 0,
           sugFilter: "all", lineFilter: "", lineSort: "util", trendItem: null, chart: null};

const n1 = v => v == null || isNaN(v) ? "–" : Math.abs(v) >= 1000 ? Math.round(v).toLocaleString("pl") : Math.abs(v) >= 100 ? Math.round(v) : (+v).toFixed(1).replace(/\.0$/, "");
const pct = v => v == null ? "–" : Math.round(v * 100) + "%";
function watts(w) {
  if (w == null) return "–";
  const u = ["W", "kW", "MW", "GW", "TW"]; let i = 0;
  while (Math.abs(w) >= 1000 && i < u.length - 1) { w /= 1000; i++; }
  return (w < 10 ? w.toFixed(2) : w < 100 ? w.toFixed(1) : Math.round(w)) + " " + u[i];
}
function mins(m) {
  if (m == null) return "–";
  if (m < 60) return Math.round(m) + " min";
  if (m < 60 * 48) return (m / 60).toFixed(1).replace(".", ",") + " h";
  return Math.round(m / 1440) + " dni";
}
function ago(t) {
  if (!t) return "–";
  const s = Date.now() / 1000 - t;
  if (s < 60) return "przed chwilą";
  if (s < 3600) return Math.round(s / 60) + " min temu";
  return Math.round(s / 3600) + " h temu";
}
const pretty = n => n ? (n.charAt(0).toUpperCase() + n.slice(1)).replace(/-/g, " ") : "";
function wikiName(n) { return (n.charAt(0).toUpperCase() + n.slice(1)).replace(/-/g, "_"); }
function ico(name) {
  if (!name) return "";
  const ini = esc(name.split("-").map(w => w[0]).join("").slice(0, 2).toUpperCase());
  return `<img class="ico" src="https://wiki.factorio.com/images/${encodeURIComponent(wikiName(name))}.png" alt="${ini}" loading="lazy" referrerpolicy="no-referrer" onerror="this.outerHTML='<span class=ico>${ini}</span>'">`;
}
const item = (n, label) => `<span class="item">${ico(n)}<span>${esc(label || pretty(n))}</span></span>`;
function parseGps(g) {
  const m = /\[gps=(-?\d+),(-?\d+),?([^\]]*)\]/.exec(g || "");
  return m ? {x: +m[1], y: +m[2], s: m[3] || "nauvis"} : null;
}
function loc(g) {
  const p = parseGps(g);
  if (!p) return "";
  return `<span class="chip loc" data-gps="${esc(g)}" title="Pokaż na mapie">${svg("pin")}${p.x}, ${p.y}</span>` +
    `<button class="btn small icon" data-copy="${esc(g)}" title="Kopiuj tag GPS na czat w grze">${svg("copy")}</button>`;
}
const locs = (list, n = 2) => (list || []).filter(Boolean).slice(0, n).map(loc).join("");
function empty(title, text) {
  return `<div class="empty"><img src="img/allgood.svg" alt=""><b>${esc(title)}</b><span>${esc(text || "")}</span></div>`;
}
function card(title, body, opts = {}) {
  return `<div class="card ${opts.cls || ""}" ${opts.id ? `id="${opts.id}"` : ""}>
    <div class="card-h"><h3>${title}</h3>${opts.badge != null ? `<span class="badge ${opts.badgeCls || ""}">${opts.badge}</span>` : ""}
    ${opts.hint ? `<span class="hint">${esc(opts.hint)}</span>` : ""}${opts.right ? `<div class="right">${opts.right}</div>` : ""}</div>
    <div class="card-b">${body}</div></div>`;
}
function table(cols, rows, opts = {}) {
  if (!rows.length) return opts.empty || empty("Brak", "Nic tu nie ma — i dobrze.");
  const cl = cols.map(c => c.split("|")[1] || "");
  return `<div class="scroll"><table class="tbl"><thead><tr>${cols.map(c => `<th class="${c.split("|")[1] || ""}">${c.split("|")[0]}</th>`).join("")}</tr></thead>
    <tbody>${rows.map(r => `<tr>${r.map((v, i) => `<td class="${cl[i]}">${v ?? ""}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}
function bigRing(v) {
  const r = 46, c = 2 * Math.PI * r, off = c * (1 - Math.max(0, Math.min(1, v || 0)));
  return `<svg viewBox="0 0 110 110" width="110" height="110"><defs><linearGradient id="rg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffb547"/><stop offset="1" stop-color="#ff6a2b"/></linearGradient></defs>
    <circle cx="55" cy="55" r="${r}" fill="none" stroke="var(--panel2)" stroke-width="10"/>
    <circle cx="55" cy="55" r="${r}" fill="none" stroke="url(#rg)" stroke-width="10" stroke-linecap="round" stroke-dasharray="${c}" stroke-dashoffset="${off}" transform="rotate(-90 55 55)"/></svg>`;
}
function kpi(icon, k, v, s, cls = "", extra = "") {
  return `<div class="kpi ${cls}"><div class="k">${svg(icon)}${k}</div><div class="v">${v}</div><div class="s">${s}</div>${extra}</div>`;
}
function meter(v, cls = "") { return `<div class="meter ${cls}"><i style="width:${Math.max(0, Math.min(100, (v || 0) * 100)).toFixed(1)}%"></i></div>`; }
const SEV_ICON = {high: "alert", mid: "alert", low: "up"};
const KIND = {build: ["build", "Budowa"], rebalance: ["production", "Balans"], upgrade: ["up", "Ulepszenie"], modules: ["modules", "Moduły"],
              power: ["power", "Prąd"], mining: ["mining", "Wydobycie"], research: ["research", "Badania"], logistics: ["ghost", "Logistyka"]};

function toast(t) { const el = $("#toast"); el.textContent = t; el.classList.add("on"); clearTimeout(toast.t); toast.t = setTimeout(() => el.classList.remove("on"), 2600); }

async function api(path, opts) {
  const r = await fetch(BASE + path, Object.assign({cache: "no-cache"}, opts));
  if (!r.ok) throw new Error(r.status === 404 ? "brak danych" : "HTTP " + r.status);
  return r.json();
}

function buildNav() {
  const html = VIEWS.map(([id, label, icon]) => `<a class="nav-item" href="#/${id}" data-v="${id}">${svg(icon)}<span>${label}</span><span class="badge" data-badge="${id}" hidden></span></a>`).join("");
  $("#nav").innerHTML = html;
  $("#mnav").innerHTML = VIEWS.map(([id, label, icon]) => `<a href="#/${id}" data-v="${id}">${svg(icon)}<span>${label}</span></a>`).join("");
  $(".brand small").textContent = location.hostname;
}

function setBadge(id, n, cls) {
  const b = $(`[data-badge="${id}"]`);
  if (!b) return;
  b.hidden = !n;
  b.textContent = n;
  b.className = "badge " + (cls || "");
}

function route() {
  const v = (location.hash.match(/#\/(\w+)/) || [])[1] || "overview";
  S.view = VIEWS.some(x => x[0] === v) ? v : "overview";
  $$(".view").forEach(el => el.classList.toggle("active", el.dataset.view === S.view));
  $$("[data-v]").forEach(el => el.classList.toggle("active", el.dataset.v === S.view));
  $("#title").textContent = VIEWS.find(x => x[0] === S.view)[1];
  renderView(S.view);
  window.scrollTo({top: 0});
}

function renderView(v, force) {
  if (!S.data) return;
  if (!force && S.rendered[v] === S.data.generated && v !== "map") return;
  const el = $(`.view[data-view="${v}"]`);
  const fn = {overview: vOverview, suggestions: vSuggestions, map: vMap, production: vProduction,
              power: vPower, mining: vMining, research: vResearch, trends: vTrends}[v];
  fn(el);
  S.rendered[v] = S.data.generated;
}

function vOverview(el) {
  const d = S.data, s = d.summary, R = d.research || {}, cur = R.current;
  const top = (d.suggestions || []).slice(0, 5);
  const alerts = d.alerts || [];
  const loadV = s.capacity_w ? s.power_w / s.capacity_w : null;
  const mood = s.working_pct >= .85 ? "działa jak w zegarku" : s.working_pct >= .65 ? "pracuje, ale coś ją hamuje" : "ma poważne zatory";
  el.innerHTML = `
  <div class="hero">
    <div class="txt">
      <div class="eyebrow">Czas gry ${esc(d.game_time)} · Factorio ${esc(d.game_version || "")}</div>
      <h2>Fabryka ${mood} — <span class="g">${pct(s.working_pct)}</span> maszyn pracuje</h2>
      <p>${s.shortages ? `<b>${s.shortages}</b> rodzajów braków, ` : ""}${s.deficits ? `<b>${s.deficits}</b> deficytów, ` : ""}<b>${s.suggestions}</b> sugestii do poprawy.
        Dane z zapisu <b>${esc(d.save)}</b> (${ago(d.save_time)}).</p>
      <div class="chips">
        <span class="chip">${svg("cpu")}<b>${s.machines}</b> maszyn</span>
        <span class="chip">${svg("box")}<b>${(s.entities || 0).toLocaleString("pl")}</b> obiektów</span>
        ${s.ghosts ? `<span class="chip">${svg("ghost")}<b>${s.ghosts}</b> duchów</span>` : ""}
        <a class="chip on" href="#/map" style="text-decoration:none">${svg("map")}Otwórz mapę</a>
      </div>
    </div>
    <div class="art"><img src="img/factory.svg" alt=""></div>
  </div>
  <div class="kpis">
    ${kpi("cpu", "Maszyny pracują", pct(s.working_pct), `${s.working} z ${s.machines}`, s.working_pct < .65 ? "bad" : s.working_pct < .85 ? "warn" : "good", meter(s.working_pct, s.working_pct < .65 ? "bad" : "good"))}
    ${kpi("power", "Zużycie prądu", watts(s.power_w), loadV != null ? `${pct(loadV)} maks. mocy (${watts(s.capacity_w)})` : `produkcja ${watts(s.power_prod_w)}`, loadV > .9 || s.low_power ? "bad" : loadV > .75 ? "warn" : "", loadV != null ? meter(loadV, loadV > .9 ? "bad" : "") : "")}
    ${kpi("alert", "Braki składników", s.shortages, s.shortages ? "rodzajów — zobacz Produkcję" : "wszystko dociera", s.shortages ? "bad" : "good")}
    ${kpi("suggestions", "Sugestie", s.suggestions, "pomysłów na poprawę", s.suggestions ? "warn" : "good")}
    ${kpi("research", "Badanie", cur ? pct(cur.progress) : "—", cur ? esc(pretty(cur.name)) + (cur.eta_min ? ` · ~${mins(cur.eta_min)}` : "") : "nic się nie bada", cur ? "" : "bad", cur ? meter(cur.progress) : "")}
  </div>
  <div class="grid2">
    ${card("Najważniejsze sugestie", top.length ? `<div class="list">${top.map(sugRow).join("")}</div>
       <div style="margin-top:12px"><a class="btn small" href="#/suggestions">Wszystkie sugestie (${(d.suggestions || []).length})</a></div>` : empty("Brak sugestii", "Fabryka jest dobrze zbalansowana."),
       {badge: (d.suggestions || []).length, badgeCls: "mid"})}
    ${card("Alerty", alerts.length ? `<div class="list">${alerts.map(a => `
      <div class="row"><div class="sev ${a.level}">${svg(SEV_ICON[a.level])}</div><div class="body"><div class="d" style="color:var(--text)">${esc(a.text)}</div></div>
      <div class="actions">${loc(a.gps)}</div></div>`).join("")}</div>` : empty("Wszystko gra", "Brak alertów."), {badge: alerts.length, badgeCls: alerts.length ? "bad" : "good"})}
  </div>
  <div class="grid2">
    ${card("Produkcja nauki", table(["Pakiet", "Produkcja/min|num", "Zużycie/min|num", "Bilans|num"], (d.science || []).map(x => [item(x.name), n1(x.prod), n1(x.cons), `<span class="${x.prod - x.cons < -0.5 ? "neg" : "pos"}">${x.prod - x.cons >= 0 ? "+" : ""}${n1(x.prod - x.cons)}</span>`]), {empty: empty("Brak nauki", "Nie produkujesz jeszcze pakietów.")}), {hint: "średnia z 10 min"})}
    ${card("Najwięcej produkujesz", table(["Przedmiot", "Produkcja/min|num", "Zużycie/min|num"], (d.top_production || []).slice(0, 10).map(x => [item(x.name), n1(x.prod), n1(x.cons)])), {hint: "top 10"})}
  </div>`;
}

function sugRow(x) {
  const k = KIND[x.kind] || ["suggestions", ""];
  return `<div class="row"><div class="sev ${x.severity}">${svg(k[0])}</div>
    <div class="body"><div class="t">${x.item ? ico(x.item) + " " : ""}${esc(x.title)}</div><div class="d">${esc(x.detail)}</div></div>
    <div class="actions">${loc(x.gps)}</div></div>`;
}

function vSuggestions(el) {
  const all = S.data.suggestions || [];
  const kinds = [["all", "Wszystkie"], ["high", "Pilne"], ["build", "Budowa"], ["power", "Prąd"], ["mining", "Wydobycie"], ["research", "Badania"], ["upgrade", "Ulepszenia"], ["modules", "Moduły"], ["rebalance", "Balans"], ["logistics", "Logistyka"]]
    .filter(([k]) => k === "all" || k === "high" ? true : all.some(s => s.kind === k));
  const f = S.sugFilter;
  const list = all.filter(s => f === "all" || (f === "high" ? s.severity === "high" : s.kind === f));
  el.innerHTML = card("Sugestie dla Twojej fabryki", `
    <div class="seg" style="margin-bottom:14px;flex-wrap:wrap">${kinds.map(([k, l]) => `<button class="${k === f ? "on" : ""}" data-sug="${k}">${l}</button>`).join("")}</div>
    ${list.length ? `<div class="list">${list.map(sugRow).join("")}</div>` : empty("Nic do poprawy", "W tej kategorii wszystko wygląda dobrze.")}`,
    {badge: all.length, badgeCls: "mid", hint: "wyliczone z prędkości maszyn, receptur i statusów"});
  $$("[data-sug]", el).forEach(b => b.onclick = () => { S.sugFilter = b.dataset.sug; vSuggestions(el); });
}

function vProduction(el) {
  const d = S.data;
  const sh = d.shortages || [];
  el.innerHTML = `
  ${card("Braki — na co czekają maszyny", sh.length ? `<div class="list">${sh.map(x => `
    <div class="row"><div class="sev ${x.machines >= 5 ? "high" : "mid"}">${svg("alert")}</div>
      <div class="body">
        <div class="t">${item(x.item)} <span class="badge bad">${x.machines} maszyn stoi</span>
          <span class="muted" style="font-weight:400;font-size:12.5px">prod. ${n1(x.prod)}/min · zużycie ${n1(x.cons)}/min</span></div>
        <div class="chain">${(x.cause || []).map((c, i, a) => `${i ? '<span class="arrow">→</span>' : ""}<span class="node ${i === a.length - 1 ? "root" : ""}"><b>${esc(pretty(c.item))}</b>: ${esc(c.reason)}</span>`).join("")}</div>
        <div class="chain">${x.recipes.slice(0, 5).map(r => `<span class="chip">${esc(pretty(r.recipe))} <b>×${r.machines}</b></span>`).join("")}</div>
      </div>
      <div class="actions">${locs(x.recipes.flatMap(r => r.gps), 1)}</div></div>`).join("")}</div>` : empty("Brak braków", "Wszystkie maszyny dostają składniki."),
    {badge: sh.length, badgeCls: sh.length ? "bad" : "good", hint: "łańcuch pokazuje prawdziwą przyczynę"})}
  <div class="grid2">
    ${card("Deficyty", table(["Przedmiot", "Prod./min|num", "Zużycie/min|num", "Brakuje|num"], (d.deficits || []).map(x => [
      `<a href="#/trends" data-trend="${esc(x.item)}" style="text-decoration:none">${item(x.item)}</a>`, n1(x.prod), n1(x.cons), `<span class="neg">−${n1(x.deficit)}</span>`]),
      {empty: empty("Bez deficytów", "Produkujesz tyle, ile zużywasz.")}), {badge: (d.deficits || []).length, hint: "zużycie > produkcja (10 min)"})}
    ${card("Zatory — pełne wyjście", table(["Receptura", "Zablokowane|num", "Gdzie"], (d.blocked || []).map(x => [item(x.recipe), `${x.machines} / ${x.of}`, locs(x.gps, 1)]),
      {empty: empty("Bez zatorów", "Wszystko jest odbierane na bieżąco.")}), {badge: (d.blocked || []).length, hint: "nadprodukcja lub pełna taśma"})}
  </div>
  <div id="linesCard"></div>`;
  renderLines();
}

function renderLines() {
  const box = $("#linesCard");
  if (!box) return;
  const f = S.lineFilter.toLowerCase();
  let rows = (S.data.lines || []).filter(l => !f || l.recipe.toLowerCase().includes(f) || (l.product || "").toLowerCase().includes(f));
  const sorters = {util: (a, b) => a.utilization - b.utilization, machines: (a, b) => b.machines - a.machines, name: (a, b) => a.recipe.localeCompare(b.recipe)};
  rows = rows.slice().sort(sorters[S.lineSort]);
  box.innerHTML = card("Linie produkcyjne", table(["Receptura", "Maszyny|num", "Wykorzystanie", "Maks./min|num", "Faktycznie/min|num", "Statusy", "Problemy"], rows.map(l => [
    `${item(l.recipe)}<div class="muted" style="font-size:12px;margin-top:2px">${Object.entries(l.entities).map(([k, v]) => esc(pretty(k)) + " ×" + v).join(", ")}</div>`,
    `${l.working}/${l.machines}`,
    `<div style="min-width:110px">${meter(l.utilization, l.utilization < .5 ? "bad" : l.utilization > .85 ? "good" : "")}<span class="muted" style="font-size:12px">${pct(l.utilization)}</span></div>`,
    n1(l.max_per_min), n1(l.actual_per_min),
    Object.entries(l.status).map(([k, v]) => `<span class="chip">${esc(k)} <b>${v}</b></span>`).join(" "),
    l.problems.slice(0, 2).map(p => `<div style="display:flex;gap:6px;align-items:center;margin:2px 0"><span class="muted" style="font-size:12px">${esc(p.status)}</span>${locs(p.gps, 1)}</div>`).join("")])),
    {badge: rows.length, right: `<div class="seg">${[["util", "Najgorsze"], ["machines", "Największe"], ["name", "A–Z"]].map(([k, l]) => `<button class="${S.lineSort === k ? "on" : ""}" data-lsort="${k}">${l}</button>`).join("")}</div>
      <label class="search">${svg("search")}<input id="lineSearch" placeholder="Szukaj receptury…" value="${esc(S.lineFilter)}"></label>`});
  const inp = $("#lineSearch");
  inp.oninput = () => { S.lineFilter = inp.value; const pos = inp.selectionStart; renderLines(); const n = $("#lineSearch"); n.focus(); n.setSelectionRange(pos, pos); };
  $$("[data-lsort]", box).forEach(b => b.onclick = () => { S.lineSort = b.dataset.lsort; renderLines(); });
}

function bars(list, total, cls = "") {
  const max = Math.max(...list.map(x => x[1]), 1);
  return `<div class="bars">${list.map(([k, v]) => `<div class="bar-row"><span class="name">${ico(k)}${esc(pretty(k))}</span>
    <div class="bar ${cls}"><i style="width:${(v / max * 100).toFixed(1)}%"></i></div><span class="num">${watts(v)}</span></div>`).join("")}</div>`;
}

function vPower(el) {
  const d = S.data, nets = d.power || [];
  el.innerHTML = `<div class="kpis">
    ${kpi("power", "Zużycie", watts(d.summary.power_w), "suma wszystkich sieci")}
    ${kpi("power", "Produkcja", watts(d.summary.power_prod_w), "średnia z 1 min")}
    ${kpi("power", "Maks. moc", watts(d.summary.capacity_w), "wszystkich generatorów")}
    ${kpi("alert", "Bez prądu", d.summary.low_power, "maszyn bez prądu lub ze słabym prądem", d.summary.low_power ? "bad" : "good")}
  </div>
  ${card("Sieci elektryczne", nets.length ? nets.map(n => `
    <div class="net">
      <div class="top-line">
        <div><div class="muted" style="font-size:12px">Sieć #${n.id} · ${n.poles} słupów</div><div class="big">${watts(n.consumption_w)} <span class="muted" style="font-size:14px;font-weight:500">/ ${watts(n.capacity_w || n.production_w)}</span></div></div>
        ${n.load != null ? `<div style="flex:1;min-width:180px"><div class="muted" style="font-size:12px">Obciążenie ${pct(n.load)}</div>${meter(n.load, n.load > .9 ? "bad" : n.load < .6 ? "good" : "")}</div>` : ""}
        ${n.accumulators ? `<div><div class="muted" style="font-size:12px">Akumulatory ×${n.accumulators}</div><b>${pct(n.acc_charge)}</b> naładowane</div>` : ""}
        <div class="actions">${loc(n.gps)}</div>
      </div>
      <div class="grid2" style="margin-top:6px;gap:24px">
        <div><div class="muted" style="font-size:12px;margin-top:10px">Najwięksi odbiorcy</div>${bars(n.top_consumers)}</div>
        <div><div class="muted" style="font-size:12px;margin-top:10px">Źródła</div>${bars(n.producers, 0, "teal")}</div>
      </div>
    </div>`).join("") : empty("Brak sieci", "Nie znaleziono sieci elektrycznych."), {badge: nets.length})}`;
}

function vMining(el) {
  const sites = S.data.mining || [];
  const tot = {};
  sites.forEach(s => { if (s.resource !== "(wyczerpane)") { tot[s.resource] = tot[s.resource] || {drills: 0, rate: 0, rem: 0, inf: s.infinite}; tot[s.resource].drills += s.drills; tot[s.resource].rate += s.rate_per_min || 0; tot[s.resource].rem += s.remaining || 0; } });
  el.innerHTML = `<div class="kpis">${Object.entries(tot).map(([k, t]) => `<div class="kpi"><div class="k">${ico(k)} ${esc(pretty(k))}</div>
      <div class="v">${n1(t.rate)}<span class="muted" style="font-size:14px">/min</span></div><div class="s">${t.drills} wierteł · ${t.inf ? "∞" : n1(t.rem) + " zostało"}</div></div>`).join("")}</div>
  ${card("Pola wydobywcze", table(["Surowiec", "Wiertła|num", "Pracuje|num", "Wyczerpane|num", "Zostało|num", "Wydobycie/min|num", "Starczy na", "Gdzie"], sites.map(x => [
    item(x.resource), x.drills, x.working, x.depleted ? `<span class="neg">${x.depleted}</span>` : 0,
    x.infinite ? "∞" : n1(x.remaining), n1(x.rate_per_min),
    x.minutes_left == null ? "–" : `<div style="min-width:100px"><b class="${x.minutes_left < 120 ? "neg" : x.minutes_left < 600 ? "" : "pos"}">${mins(x.minutes_left)}</b>${meter(Math.min(1, x.minutes_left / 1440), x.minutes_left < 120 ? "bad" : "good")}</div>`,
    locs([x.gps].concat(x.problem_gps || []), 1)])), {badge: sites.length, hint: "szacunek: ruda pod wiertłami ÷ tempo"})}`;
}

function vResearch(el) {
  const R = S.data.research || {}, cur = R.current;
  el.innerHTML = `<div class="grid2">
    ${card("Aktualne badanie", cur ? `
      <div style="display:flex;gap:18px;align-items:center">
        <div style="position:relative;width:110px;height:110px;flex:none">${bigRing(cur.progress)}
          <div style="position:absolute;inset:0;display:grid;place-items:center;font:700 22px var(--display)">${pct(cur.progress)}</div></div>
        <div><div style="font:600 18px var(--display)">${ico(cur.name)} ${esc(pretty(cur.name))}${cur.level > 1 ? " " + cur.level : ""}</div>
          <div class="muted" style="margin:4px 0 10px">${cur.eta_min ? "Koniec za ~" + mins(cur.eta_min) : "ETA nieznane"} · ${cur.units} jednostek</div>
          <div class="chain">${cur.ingredients.map(i => `<span class="chip">${ico(i.name)} <b>×${i.amount}</b></span>`).join("")}</div></div>
      </div>` : empty("Nic się nie bada", "Ustaw kolejkę badań w grze (T)."))}
    ${card("Laboratoria", `<div class="kpis" style="grid-template-columns:1fr 1fr">${kpi("research", "Pracuje", `${R.labs_working}/${R.labs}`, "laboratoriów", R.labs && R.labs_working < R.labs ? "warn" : "good", meter(R.labs ? R.labs_working / R.labs : 0))}
      ${kpi("check", "Zbadane", R.researched, "technologii")}</div>
      <div class="chain" style="margin-top:12px">${Object.entries(R.labs_status || {}).map(([k, v]) => `<span class="chip">${esc(k)} <b>${v}</b></span>`).join("")}</div>
      ${Object.keys(R.labs_missing || {}).length ? `<div class="chain" style="margin-top:8px"><span class="neg">Brakuje:</span>${Object.entries(R.labs_missing).map(([k, v]) => `<span class="chip">${ico(k)} ${v} lab.</span>`).join("")}</div>` : ""}
      <div class="chain" style="margin-top:8px">${locs(R.labs_gps, 2)}</div>`)}
  </div>
  ${card("Kolejka badań", (R.queue || []).length ? `<div class="chain">${R.queue.map((q, i) => `${i ? '<span class="arrow">→</span>' : ""}<span class="chip">${ico(q)} ${esc(pretty(q))}</span>`).join("")}</div>` : empty("Pusta kolejka", "Dodaj technologie, żeby laboratoria nie stały."))}
  ${card("Pakiety nauki", table(["Pakiet", "Produkcja/min|num", "Zużycie/min|num", "Bilans|num"], (S.data.science || []).map(x => [item(x.name), n1(x.prod), n1(x.cons), `<span class="${x.prod - x.cons < -0.5 ? "neg" : "pos"}">${n1(x.prod - x.cons)}</span>`])))}`;
}

function vTrends(el) {
  const names = Object.keys(S.data.rates || {}).sort();
  el.innerHTML = card("Trendy z ostatnich 24 h", `
    <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px;align-items:center">
      <label class="search">${svg("search")}<input id="trendInput" list="trendItems" placeholder="Przedmiot, np. iron-plate" value="${esc(S.trendItem || "")}"></label>
      <datalist id="trendItems">${names.map(n => `<option value="${esc(n)}">`).join("")}</datalist>
      <button class="btn small" id="trendGo">Pokaż</button>
      <button class="btn small" id="trendAll">Ogólne</button>
      <span class="muted" id="trendLabel"></span>
    </div>
    <div class="chart-box"><canvas id="chart"></canvas></div>`);
  $("#trendGo").onclick = () => showTrend($("#trendInput").value.trim() || null);
  $("#trendInput").onkeydown = e => { if (e.key === "Enter") showTrend(e.target.value.trim() || null); };
  $("#trendAll").onclick = () => showTrend(null);
  showTrend(S.trendItem);
}

async function showTrend(it) {
  S.trendItem = it;
  if (!window.Chart) { setTimeout(() => showTrend(it), 300); return; }
  const hist = await api("api/history" + (it ? "?item=" + encodeURIComponent(it) : ""));
  const cv = $("#chart");
  if (!cv) return;
  $("#trendLabel").textContent = it ? pretty(it) : "Prąd i wykorzystanie maszyn";
  const labels = hist.map(h => new Date(h.t * 1000).toLocaleTimeString("pl", {hour: "2-digit", minute: "2-digit"}));
  const ctx = cv.getContext("2d");
  const grad = (c1) => { const g = ctx.createLinearGradient(0, 0, 0, 320); g.addColorStop(0, c1 + "55"); g.addColorStop(1, c1 + "00"); return g; };
  const ds = it
    ? [{label: "Produkcja/min", data: hist.map(h => h.v[0]), borderColor: "#34d399", backgroundColor: grad("#34d399"), fill: true},
       {label: "Zużycie/min", data: hist.map(h => h.v[1]), borderColor: "#ff8a3d", backgroundColor: grad("#ff8a3d"), fill: true}]
    : [{label: "Produkcja prądu (MW)", data: hist.map(h => h.power[0] / 1e6), borderColor: "#ffb547", backgroundColor: grad("#ffb547"), fill: true},
       {label: "Zużycie prądu (MW)", data: hist.map(h => h.power[1] / 1e6), borderColor: "#60a5fa", backgroundColor: grad("#60a5fa"), fill: true},
       {label: "Pracujące maszyny %", data: hist.map(h => h.working_pct * 100), borderColor: "#34d399", yAxisID: "y2", borderDash: [5, 4]}];
  if (S.chart) S.chart.destroy();
  const css = getComputedStyle(document.documentElement);
  const tc = css.getPropertyValue("--muted").trim(), lc = css.getPropertyValue("--line").trim();
  S.chart = new Chart(cv, {
    type: "line",
    data: {labels, datasets: ds.map(x => Object.assign({tension: .35, pointRadius: 0, pointHoverRadius: 4, borderWidth: 2.2}, x))},
    options: {responsive: true, maintainAspectRatio: false, interaction: {mode: "index", intersect: false},
      plugins: {legend: {labels: {color: tc, usePointStyle: true, boxWidth: 8, font: {family: "Inter"}}},
                tooltip: {backgroundColor: "rgba(13,18,28,.95)", borderColor: "rgba(255,255,255,.1)", borderWidth: 1, padding: 10, titleFont: {family: "Inter"}, bodyFont: {family: "Inter"}}},
      scales: {x: {ticks: {color: tc, maxTicksLimit: 10}, grid: {color: lc}},
               y: {ticks: {color: tc}, grid: {color: lc}, beginAtZero: true},
               ...(it ? {} : {y2: {position: "right", min: 0, max: 100, ticks: {color: "#34d399"}, grid: {display: false}}})}}
  });
}

function vMap(el) {
  if (!el.dataset.init) {
    el.dataset.init = "1";
    el.innerHTML = `<div class="mapwrap" id="mapwrap"></div>`;
    FMap.init($("#mapwrap"), {onCopy: g => copyGps(g), icon: ico, pretty, esc, svg});
  }
  loadMap();
  if (S.pendingFocus) { FMap.focus(S.pendingFocus.x, S.pendingFocus.y, S.pendingFocus.s); S.pendingFocus = null; }
}

async function loadMap() {
  if (S.mapLoaded === S.data.generated) return;
  try {
    S.map = await api("api/map");
    S.mapLoaded = S.data.generated;
    FMap.load(S.map);
    if (S.pendingFocus) { FMap.focus(S.pendingFocus.x, S.pendingFocus.y, S.pendingFocus.s); S.pendingFocus = null; }
  } catch (e) { FMap.message("Mapa niedostępna: " + e.message); }
}

function showOnMap(g) {
  const p = parseGps(g);
  if (!p) return;
  S.pendingFocus = p;
  if (S.view === "map") { FMap.focus(p.x, p.y, p.s); S.pendingFocus = null; }
  else location.hash = "#/map";
}

function copyGps(g) {
  const done = () => toast("Skopiowano " + g + " — wklej na czat w grze");
  if (navigator.clipboard) navigator.clipboard.writeText(g).then(done, () => toast(g));
  else toast(g);
}

function renderChrome() {
  const st = S.status || {}, d = S.data;
  const pill = $("#statusPill");
  pill.className = "pill" + (st.running ? " busy" : st.last_error ? " err" : "");
  $("#statusText").textContent = st.running ? "Zbieram dane…" : st.last_error ? "Błąd zrzutu" : d ? "Zrzut " + ago(d.generated) : "Brak danych";
  pill.title = st.last_error || "";
  $("#subtitle").textContent = d ? `Czas gry ${d.game_time} · zapis ${d.save} (${ago(d.save_time)})` : "";
  $("#sideFoot").innerHTML = d ? `Zapis <b>${esc(d.save)}</b><br>${ago(d.save_time)} · co ${Math.round((st.interval || 300) / 60)} min` : esc(st.last_error || "Czekam na pierwszy zrzut…");
  if (d) {
    setBadge("suggestions", (d.suggestions || []).filter(s => s.severity !== "low").length, "mid");
    setBadge("production", d.summary.shortages, "bad");
    setBadge("power", d.summary.low_power, "bad");
    setBadge("map", (S.map && S.map.markers.length) || 0, "");
  }
}

async function loadLatest() {
  try {
    S.data = await api("api/latest");
    renderChrome();
    renderView(S.view, true);
  } catch (e) {
    $(`.view[data-view="${S.view}"]`).innerHTML = card("Czekam na dane", `<div class="empty"><img src="img/factory.svg" alt="" style="width:320px;opacity:.9"><b>Pierwszy zrzut w toku</b><span>${esc((S.status && S.status.last_error) || "Serwer-cień ładuje kopię zapisu. To zajmuje zwykle 1–3 minuty.")}</span></div>`);
  }
}

async function poll() {
  try {
    S.status = await api("api/status");
    if (S.status.generated && (!S.data || S.status.generated !== S.data.generated)) await loadLatest();
    else renderChrome();
  } catch (e) { $("#statusText").textContent = "Offline"; }
}

async function refreshNow() {
  const b = $("#refreshBtn");
  b.disabled = true;
  try {
    await api("api/refresh", {method: "POST"});
    toast("Zlecono nowy zrzut — wyniki za ok. 1–2 min");
    const t0 = S.data && S.data.generated;
    for (let i = 0; i < 60; i++) {
      await new Promise(r => setTimeout(r, 4000));
      await poll();
      if ((S.data && S.data.generated) !== t0 || (S.status && !S.status.running && S.status.last_error && i > 3)) break;
    }
  } finally { b.disabled = false; }
}

function setTheme(t) {
  document.documentElement.dataset.theme = t;
  try { localStorage.setItem("theme", t); } catch (e) {}
  $("#themeBtn").innerHTML = svg(t === "light" ? "moon" : "sun");
  if (S.view === "trends" && S.data) showTrend(S.trendItem);
}

document.addEventListener("click", e => {
  const l = e.target.closest(".chip.loc");
  if (l) { e.preventDefault(); showOnMap(l.dataset.gps); return; }
  const c = e.target.closest("[data-copy]");
  if (c) { e.preventDefault(); copyGps(c.dataset.copy); return; }
  const t = e.target.closest("[data-trend]");
  if (t) { S.trendItem = t.dataset.trend; S.rendered.trends = null; }
});

function init() {
  buildNav();
  $("#refreshBtn").innerHTML = svg("refresh") + "<span>Zrzut teraz</span>";
  $("#refreshBtn").onclick = refreshNow;
  $("#themeBtn").onclick = () => setTheme(document.documentElement.dataset.theme === "light" ? "dark" : "light");
  setTheme(document.documentElement.dataset.theme || "dark");
  $$(".view").forEach(v => v.innerHTML = `<div class="kpis">${'<div class="skeleton"></div>'.repeat(4)}</div><div class="skeleton" style="height:300px"></div>`);
  window.addEventListener("hashchange", route);
  route();
  poll();
  setInterval(() => { if (!document.hidden) poll(); }, 20000);
  setInterval(renderChrome, 30000);
}

init();

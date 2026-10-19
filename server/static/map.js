"use strict";

const FMap = (() => {
  const ORE = {"iron-ore": "#5f84a8", "copper-ore": "#c8693a", "coal": "#4b4b55", "stone": "#b09868",
               "uranium-ore": "#5fd13f", "crude-oil": "#b26bdb"};
  const CAT = {
    rail: "#8a8f99", pipe: "#3d7fc4", belt: "#e8b53a", pole: "#c9a46a", inserter: "#a7b2bf",
    assembler: "#6f93c0", furnace: "#d08a46", drill: "#7fa85a", lab: "#c6a6f5", beacon: "#9b6cf6",
    power: "#f2cf4b", chest: "#a87d4c", logistics: "#4fd6c4", defense: "#b45a5a", circuit: "#6b7a90",
    train: "#f472b6", other: "#5b6474", ghost: "#7dd3fc",
  };
  const LAYERS = [
    ["ores", "Ruda", "#c8693a", ["__ores"]],
    ["buildings", "Budynki", "#6f93c0", ["assembler", "furnace", "drill", "lab", "beacon", "power", "chest", "logistics", "defense", "circuit", "train", "other"]],
    ["belts", "Taśmy", "#e8b53a", ["belt", "inserter"]],
    ["pipes", "Rury", "#3d7fc4", ["pipe"]],
    ["rails", "Tory", "#8a8f99", ["rail"]],
    ["poles", "Słupy", "#c9a46a", ["pole"]],
    ["ghosts", "Duchy", "#7dd3fc", ["ghost"]],
    ["problems", "Problemy", "#f87171", ["__markers"]],
  ];
  const DRAW_ORDER = ["rail", "pipe", "belt", "pole", "chest", "circuit", "other", "defense", "logistics", "power",
                      "train", "beacon", "lab", "drill", "furnace", "assembler", "inserter", "ghost"];
  const SEV = ["#f87171", "#fbbf24", "#60a5fa"];
  const SEV_NAME = ["krytyczne", "braki", "inne"];

  let H, wrap, cv, ctx, dpr = 1, W = 0, Hh = 0;
  let data = null, surface = "nauvis", view = {x: 0, y: 0, s: 2}, fitted = false;
  let on = {ores: true, buildings: true, belts: true, pipes: true, rails: true, poles: true, ghosts: true, problems: true};
  let sevOn = [true, true, true];
  let clusters = [], highlight = null, dirty = true, raf = 0;
  const pointers = new Map();
  let dragStart = null, pinch = null, moved = false;

  try { Object.assign(on, JSON.parse(localStorage.getItem("mapLayers") || "{}")); } catch (e) {}

  function init(el, helpers) {
    H = helpers;
    wrap = el;
    wrap.innerHTML = `
      <canvas></canvas>
      <div class="map-ui">
        <div class="layers glass" id="mLayers"></div>
        <div class="layers glass" id="mSev"></div>
        <button class="btn glass" id="mListBtn" style="border-radius:14px">${H.svg("list")}<span>Lista problemów</span></button>
        <select class="btn glass" id="mSurface" style="border-radius:14px;display:none"></select>
      </div>
      <div class="map-side glass" id="mSide"></div>
      <div class="popup glass" id="mPop"></div>
      <div class="coords glass" id="mCoords">0, 0</div>
      <div class="legend glass">${SEV.map((c, i) => `<span><i style="background:${c}"></i>${SEV_NAME[i]}</span>`).join("")}</div>
      <div class="zoom glass">
        <button id="mIn" title="Przybliż">${H.svg("plus")}</button>
        <button id="mOut" title="Oddal">${H.svg("minus")}</button>
        <button id="mFit" title="Pokaż całą fabrykę">${H.svg("target")}</button>
      </div>`;
    cv = wrap.querySelector("canvas");
    ctx = cv.getContext("2d");
    buildLayerUi();
    new ResizeObserver(resize).observe(wrap);
    cv.addEventListener("wheel", onWheel, {passive: false});
    cv.addEventListener("pointerdown", onDown);
    cv.addEventListener("pointermove", onMove);
    cv.addEventListener("pointerup", onUp);
    cv.addEventListener("pointercancel", onUp);
    cv.addEventListener("pointerleave", () => { if (!pointers.size) wrap.querySelector("#mCoords").style.opacity = .6; });
    wrap.querySelector("#mIn").onclick = () => zoomAt(W / 2, Hh / 2, 1.6);
    wrap.querySelector("#mOut").onclick = () => zoomAt(W / 2, Hh / 2, 1 / 1.6);
    wrap.querySelector("#mFit").onclick = fit;
    wrap.querySelector("#mListBtn").onclick = () => { const s = wrap.querySelector("#mSide"); s.classList.toggle("on"); renderSide(); };
    wrap.querySelector("#mSurface").onchange = e => { surface = e.target.value; fit(); };
  }

  function buildLayerUi() {
    wrap.querySelector("#mLayers").innerHTML = LAYERS.map(([k, l, c]) =>
      `<span class="chip ${on[k] ? "on" : ""}" data-layer="${k}"><i style="background:${c}"></i>${l}</span>`).join("");
    wrap.querySelectorAll("[data-layer]").forEach(b => b.onclick = () => {
      on[b.dataset.layer] = !on[b.dataset.layer];
      try { localStorage.setItem("mapLayers", JSON.stringify(on)); } catch (e) {}
      buildLayerUi(); redraw();
    });
    const counts = [0, 0, 0];
    (data && data.markers || []).forEach(m => { if (m[2] === surface) counts[m[3]]++; });
    wrap.querySelector("#mSev").innerHTML = SEV.map((c, i) =>
      `<span class="chip ${sevOn[i] ? "on" : ""}" data-sev="${i}"><i style="background:${c};border-radius:50%"></i>${SEV_NAME[i]} <b>${counts[i]}</b></span>`).join("");
    wrap.querySelectorAll("[data-sev]").forEach(b => b.onclick = () => { sevOn[+b.dataset.sev] = !sevOn[+b.dataset.sev]; buildLayerUi(); renderSide(); redraw(); });
  }

  function load(d) {
    data = d;
    const names = Object.keys(d.surfaces || {}).filter(n => d.surfaces[n].bounds);
    if (!names.includes(surface)) surface = names.includes("nauvis") ? "nauvis" : names[0] || "nauvis";
    const sel = wrap.querySelector("#mSurface");
    sel.style.display = names.length > 1 ? "" : "none";
    sel.innerHTML = names.map(n => `<option ${n === surface ? "selected" : ""}>${H.esc(n)}</option>`).join("");
    buildLayerUi();
    renderSide();
    if (!fitted) { fit(); fitted = true; } else redraw();
  }

  function message(t) {
    if (!wrap) return;
    wrap.querySelector("#mPop").innerHTML = `<h4>${H.esc(t)}</h4>`;
    wrap.querySelector("#mPop").classList.add("on");
  }

  function S() { return data && data.surfaces && data.surfaces[surface]; }

  function fit() {
    const s = S();
    if (!s || !s.bounds || !W) { redraw(); return; }
    const [x1, y1, x2, y2] = s.bounds;
    view.x = (x1 + x2) / 2;
    view.y = (y1 + y2) / 2;
    view.s = Math.max(0.05, Math.min(40, Math.min(W / (x2 - x1 + 40), Hh / (y2 - y1 + 40))));
    redraw();
  }

  function focus(x, y, surf) {
    if (surf && data && data.surfaces[surf]) { surface = surf; wrap.querySelector("#mSurface").value = surf; }
    const from = {...view}, to = {x: x + .5, y: y + .5, s: Math.max(view.s, 14)};
    const t0 = performance.now();
    highlight = {x: x + .5, y: y + .5, t: t0};
    const step = now => {
      const k = Math.min(1, (now - t0) / 450), e = 1 - Math.pow(1 - k, 3);
      view.x = from.x + (to.x - from.x) * e;
      view.y = from.y + (to.y - from.y) * e;
      view.s = from.s * Math.pow(to.s / from.s, e);
      draw();
      if (k < 1) requestAnimationFrame(step); else animateHighlight();
    };
    requestAnimationFrame(step);
  }

  function animateHighlight() {
    if (!highlight) return;
    draw();
    if (performance.now() - highlight.t < 4000) requestAnimationFrame(animateHighlight);
    else { highlight = null; draw(); }
  }

  function resize() {
    const r = wrap.getBoundingClientRect();
    dpr = window.devicePixelRatio || 1;
    W = r.width; Hh = r.height;
    cv.width = Math.round(W * dpr); cv.height = Math.round(Hh * dpr);
    if (!fitted && data) { fit(); fitted = true; }
    redraw();
  }

  function redraw() {
    dirty = true;
    if (!raf) raf = requestAnimationFrame(() => { raf = 0; if (dirty) draw(); });
  }

  const toScreen = (x, y) => [(x - view.x) * view.s + W / 2, (y - view.y) * view.s + Hh / 2];
  const toWorld = (sx, sy) => [(sx - W / 2) / view.s + view.x, (sy - Hh / 2) / view.s + view.y];

  function draw() {
    dirty = false;
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = "#0a0d14";
    ctx.fillRect(0, 0, W, Hh);
    const s = S();
    drawGrid();
    if (!s) return;
    const [wx1, wy1] = toWorld(0, 0), [wx2, wy2] = toWorld(W, Hh);
    const sc = view.s, ox = W / 2 - view.x * sc, oy = Hh / 2 - view.y * sc;

    if (on.ores && s.ores) {
      const cell = s.ore_cell || 2, size = Math.max(1, cell * sc);
      ctx.globalAlpha = .55;
      for (const [name, arr] of Object.entries(s.ores)) {
        ctx.fillStyle = ORE[name] || "#777";
        const oil = name === "crude-oil";
        for (let i = 0; i < arr.length; i += 2) {
          const x = arr[i], y = arr[i + 1];
          if (x + cell < wx1 || x > wx2 || y + cell < wy1 || y > wy2) continue;
          if (oil) {
            ctx.beginPath(); ctx.arc(x * sc + ox + size / 2, y * sc + oy + size / 2, Math.max(2, 1.5 * sc), 0, 7); ctx.fill();
          } else ctx.fillRect(x * sc + ox, y * sc + oy, size, size);
        }
      }
      ctx.globalAlpha = 1;
      if (sc > 1.2) {
        ctx.setLineDash([6, 5]); ctx.lineWidth = 1.2;
        for (const site of data.sites || []) {
          if (site.surface !== surface || !site.bbox) continue;
          const [bx1, by1, bx2, by2] = site.bbox;
          ctx.strokeStyle = (ORE[site.resource] || "#999") + "aa";
          ctx.strokeRect((bx1 - 2) * sc + ox, (by1 - 2) * sc + oy, (bx2 - bx1 + 4) * sc, (by2 - by1 + 4) * sc);
        }
        ctx.setLineDash([]);
      }
    }

    const gap = sc >= 6 ? 0.08 : 0;
    for (const cat of DRAW_ORDER) {
      const layer = LAYERS.find(l => l[3].includes(cat));
      if (!layer || !on[layer[0]]) continue;
      const arr = s.cats[cat];
      if (!arr) continue;
      const ghost = cat === "ghost";
      ctx.fillStyle = CAT[cat];
      ctx.globalAlpha = ghost ? .35 : 1;
      for (let i = 0; i < arr.length; i += 4) {
        const x = arr[i], y = arr[i + 1], w = arr[i + 2], h = arr[i + 3];
        if (x + w < wx1 || x > wx2 || y + h < wy1 || y > wy2) continue;
        const px = (x + gap) * sc + ox, py = (y + gap) * sc + oy;
        const pw = Math.max(1, (w - 2 * gap) * sc), ph = Math.max(1, (h - 2 * gap) * sc);
        ctx.fillRect(px, py, pw, ph);
      }
      if (sc >= 8 && (cat === "assembler" || cat === "furnace" || cat === "drill" || cat === "lab")) {
        ctx.fillStyle = "rgba(0,0,0,.22)";
        for (let i = 0; i < arr.length; i += 4) {
          const x = arr[i], y = arr[i + 1], w = arr[i + 2], h = arr[i + 3];
          if (x + w < wx1 || x > wx2 || y + h < wy1 || y > wy2 || w < 2) continue;
          ctx.fillRect((x + .3) * sc + ox, (y + .3) * sc + oy, (w - .6) * sc, (h - .6) * sc);
        }
        ctx.fillStyle = CAT[cat];
        for (let i = 0; i < arr.length; i += 4) {
          const x = arr[i], y = arr[i + 1], w = arr[i + 2], h = arr[i + 3];
          if (x + w < wx1 || x > wx2 || y + h < wy1 || y > wy2 || w < 2) continue;
          ctx.fillRect((x + .55) * sc + ox, (y + .55) * sc + oy, (w - 1.1) * sc, (h - 1.1) * sc);
        }
      }
      ctx.globalAlpha = 1;
    }

    clusters = [];
    if (on.problems && data.markers) drawMarkers(wx1, wy1, wx2, wy2);

    if (highlight) {
      const [hx, hy] = toScreen(highlight.x, highlight.y);
      const k = ((performance.now() - highlight.t) % 1200) / 1200;
      ctx.strokeStyle = `rgba(255,181,71,${1 - k})`;
      ctx.lineWidth = 3;
      ctx.beginPath(); ctx.arc(hx, hy, 10 + k * 34, 0, 7); ctx.stroke();
      ctx.fillStyle = "#ffb547";
      ctx.beginPath(); ctx.arc(hx, hy, 5, 0, 7); ctx.fill();
    }
  }

  function drawGrid() {
    const step = 32 * view.s;
    if (step < 14) return;
    const [wx1, wy1] = toWorld(0, 0);
    const startX = Math.floor(wx1 / 32) * 32, startY = Math.floor(wy1 / 32) * 32;
    ctx.strokeStyle = "rgba(255,255,255,.035)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let x = startX; ; x += 32) { const [sx] = toScreen(x, 0); if (sx > W) break; ctx.moveTo(Math.round(sx) + .5, 0); ctx.lineTo(Math.round(sx) + .5, Hh); }
    for (let y = startY; ; y += 32) { const [, sy] = toScreen(0, y); if (sy > Hh) break; ctx.moveTo(0, Math.round(sy) + .5); ctx.lineTo(W, Math.round(sy) + .5); }
    ctx.stroke();
  }

  function drawMarkers(wx1, wy1, wx2, wy2) {
    const cellPx = view.s >= 10 ? 0 : 30;
    const buckets = new Map();
    for (const m of data.markers) {
      if (m[2] !== surface || !sevOn[m[3]]) continue;
      const x = m[0] + .5, y = m[1] + .5;
      if (x < wx1 - 2 || x > wx2 + 2 || y < wy1 - 2 || y > wy2 + 2) continue;
      const [sx, sy] = toScreen(x, y);
      const key = cellPx ? Math.floor(sx / cellPx) + ":" + Math.floor(sy / cellPx) : m[0] + ":" + m[1];
      let c = buckets.get(key);
      if (!c) { c = {sx: 0, sy: 0, n: 0, sev: 2, items: []}; buckets.set(key, c); }
      c.sx += sx; c.sy += sy; c.n++; c.sev = Math.min(c.sev, m[3]);
      if (c.items.length < 60) c.items.push(m);
    }
    for (const c of buckets.values()) {
      c.sx /= c.n; c.sy /= c.n;
      const r = c.n > 1 ? Math.min(22, 9 + Math.log2(c.n) * 3) : 7;
      c.r = r;
      clusters.push(c);
      const col = SEV[c.sev];
      ctx.fillStyle = col + "33";
      ctx.beginPath(); ctx.arc(c.sx, c.sy, r + 5, 0, 7); ctx.fill();
      ctx.fillStyle = col;
      ctx.strokeStyle = "rgba(10,13,20,.9)";
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(c.sx, c.sy, r, 0, 7); ctx.fill(); ctx.stroke();
      if (c.n > 1) {
        ctx.fillStyle = "#0a0d14";
        ctx.font = "700 11px Inter, sans-serif";
        ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.fillText(c.n > 999 ? "999+" : String(c.n), c.sx, c.sy + .5);
      } else {
        ctx.fillStyle = "#0a0d14";
        ctx.fillRect(c.sx - 1, c.sy - 4, 2, 5);
        ctx.fillRect(c.sx - 1, c.sy + 2.5, 2, 2);
      }
    }
  }

  function gps(m) { return `[gps=${m[0]},${m[1]},${m[2]}]`; }

  function popup(c, sx, sy) {
    const pop = wrap.querySelector("#mPop");
    const groups = {};
    c.items.forEach(m => { const k = m[4]; (groups[k] = groups[k] || []).push(m); });
    pop.innerHTML = `<button class="btn small icon x" id="mPopX">${H.svg("x")}</button>
      <h4>${c.n > 1 ? `${c.n} problemów w tym miejscu` : H.esc(H.pretty(c.items[0][5]))}</h4>
      <div class="chain" style="margin:0 0 6px">${Object.entries(groups).map(([k, v]) => `<span class="chip"><i style="width:8px;height:8px;border-radius:50%;background:${SEV[v[0][3]]};display:inline-block"></i>${H.esc(k)} <b>${v.length}</b></span>`).join("")}</div>
      <div class="plist">${c.items.slice(0, 40).map(m => `<div class="p">${H.icon(m[5])} <b>${H.esc(H.pretty(m[5]))}</b> · ${H.esc(m[4])}
        ${m[6] ? `<div class="muted" style="margin-top:2px">${H.esc(m[6])}</div>` : ""}
        <div style="display:flex;gap:6px;margin-top:5px"><button class="btn small" data-mcopy="${H.esc(gps(m))}">${H.svg("copy")} GPS ${m[0]}, ${m[1]}</button>
        ${c.n > 1 ? `<button class="btn small" data-mgo="${m[0]},${m[1]}">${H.svg("target")}</button>` : ""}</div></div>`).join("")}</div>
      ${c.n > 40 ? `<div class="muted" style="font-size:12px">…i ${c.n - 40} więcej — przybliż mapę</div>` : ""}`;
    const pw = 300;
    pop.style.left = Math.max(14, Math.min(W - pw - 14, sx + 16)) + "px";
    pop.style.top = Math.max(70, Math.min(Hh - 300, sy - 20)) + "px";
    pop.classList.add("on");
    pop.querySelector("#mPopX").onclick = () => pop.classList.remove("on");
    pop.querySelectorAll("[data-mcopy]").forEach(b => b.onclick = () => H.onCopy(b.dataset.mcopy));
    pop.querySelectorAll("[data-mgo]").forEach(b => b.onclick = () => { const [x, y] = b.dataset.mgo.split(",").map(Number); pop.classList.remove("on"); focus(x, y); });
  }

  function renderSide() {
    const side = wrap && wrap.querySelector("#mSide");
    if (!side || !side.classList.contains("on") || !data) return;
    const list = (data.markers || []).filter(m => m[2] === surface && sevOn[m[3]]);
    const groups = {};
    list.forEach(m => { const k = m[3] + "|" + m[4] + "|" + m[5]; (groups[k] = groups[k] || []).push(m); });
    const rows = Object.entries(groups).sort((a, b) => a[1][0][3] - b[1][0][3] || b[1].length - a[1].length);
    side.innerHTML = `<div style="display:flex;align-items:center;margin-bottom:6px"><b style="font-family:var(--display)">Problemy (${list.length})</b>
      <button class="btn small icon" style="margin-left:auto" id="mSideX">${H.svg("x")}</button></div>
      ${rows.length ? rows.map(([k, v]) => `<div class="mrow" data-mgo="${v[0][0]},${v[0][1]}"><i style="background:${SEV[v[0][3]]}"></i>
        ${H.icon(v[0][5])}<span style="flex:1">${H.esc(H.pretty(v[0][5]))}<br><span class="muted">${H.esc(v[0][4])}</span></span><span class="badge">${v.length}</span></div>`).join("")
        : `<div class="muted">Brak problemów 🎉</div>`}`;
    side.querySelector("#mSideX").onclick = () => side.classList.remove("on");
    side.querySelectorAll("[data-mgo]").forEach(r => r.onclick = () => { const [x, y] = r.dataset.mgo.split(",").map(Number); focus(x, y); });
  }

  function zoomAt(sx, sy, f) {
    const [wx, wy] = toWorld(sx, sy);
    view.s = Math.max(0.03, Math.min(64, view.s * f));
    view.x = wx - (sx - W / 2) / view.s;
    view.y = wy - (sy - Hh / 2) / view.s;
    redraw();
  }

  function onWheel(e) {
    e.preventDefault();
    const r = cv.getBoundingClientRect();
    zoomAt(e.clientX - r.left, e.clientY - r.top, Math.exp(-e.deltaY * (e.ctrlKey ? 0.01 : 0.0018)));
  }

  function onDown(e) {
    try { cv.setPointerCapture(e.pointerId); } catch (err) {}
    pointers.set(e.pointerId, {x: e.clientX, y: e.clientY});
    moved = false;
    if (pointers.size === 1) dragStart = {x: e.clientX, y: e.clientY, vx: view.x, vy: view.y};
    if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      pinch = {d: Math.hypot(a.x - b.x, a.y - b.y), s: view.s};
    }
    cv.classList.add("drag");
  }

  function onMove(e) {
    const r = cv.getBoundingClientRect();
    const [wx, wy] = toWorld(e.clientX - r.left, e.clientY - r.top);
    const co = wrap.querySelector("#mCoords");
    co.textContent = `${Math.floor(wx)}, ${Math.floor(wy)}`;
    co.style.opacity = 1;
    if (!pointers.has(e.pointerId)) {
      cv.style.cursor = hitCluster(e.clientX - r.left, e.clientY - r.top) ? "pointer" : "";
      return;
    }
    pointers.set(e.pointerId, {x: e.clientX, y: e.clientY});
    if (pointers.size === 2 && pinch) {
      const [a, b] = [...pointers.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y);
      const mx = (a.x + b.x) / 2 - r.left, my = (a.y + b.y) / 2 - r.top;
      zoomAt(mx, my, (pinch.s * d / pinch.d) / view.s);
      moved = true;
      return;
    }
    if (dragStart) {
      const dx = e.clientX - dragStart.x, dy = e.clientY - dragStart.y;
      if (Math.abs(dx) + Math.abs(dy) > 3) moved = true;
      view.x = dragStart.vx - dx / view.s;
      view.y = dragStart.vy - dy / view.s;
      redraw();
    }
  }

  function onUp(e) {
    pointers.delete(e.pointerId);
    if (pointers.size < 2) pinch = null;
    if (!pointers.size) {
      cv.classList.remove("drag");
      if (!moved && dragStart) {
        const r = cv.getBoundingClientRect();
        const sx = e.clientX - r.left, sy = e.clientY - r.top;
        const c = hitCluster(sx, sy);
        if (c) popup(c, sx, sy);
        else wrap.querySelector("#mPop").classList.remove("on");
      }
      dragStart = null;
    } else {
      const p = [...pointers.values()][0];
      dragStart = {x: p.x, y: p.y, vx: view.x, vy: view.y};
    }
  }

  function hitCluster(sx, sy) {
    let best = null, bd = 1e9;
    for (const c of clusters) {
      const d = Math.hypot(c.sx - sx, c.sy - sy);
      if (d < c.r + 6 && d < bd) { bd = d; best = c; }
    }
    return best;
  }

  return {init, load, focus, message};
})();

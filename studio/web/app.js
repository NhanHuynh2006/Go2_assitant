/* GoVoice Studio — giao dien. Chi VE: moi tinh toan nang (ban do, A*, LLM) o backend. */
"use strict";

const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
const TOKEN = new URLSearchParams(location.search).get("token") || "";
const RCOL = ["#3ea6ff", "#ff8a3d", "#4cc38a", "#c678dd"];
const OBJ_RGB = {
  "đen": "#2a2a2a", "trắng": "#f2f2f2", "xám": "#9aa0a6", "đỏ": "#e5484d", "nâu": "#a0622d",
  "cam": "#ff8b2b", "vàng": "#f2c94c", "xanh lá": "#46b864", "xanh dương": "#3d7be6",
  "tím": "#9b59d0", "hồng": "#ff7eb6", "xanh": "#3d9be6",
};

/* ------------------------------------------------------------------ API */
async function api(path, body) {
  const opt = { method: body === undefined ? "GET" : "POST", headers: {} };
  if (TOKEN) opt.headers["x-token"] = TOKEN;
  if (body !== undefined) { opt.headers["content-type"] = "application/json"; opt.body = JSON.stringify(body); }
  const r = await fetch(path, opt);
  if (r.status === 204) return null;
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.headers.get("content-type")?.includes("json") ? r.json() : r;
}
function toast(msg, bad) {
  const t = $("#toast");
  t.textContent = msg; t.className = "toast on" + (bad ? " bad" : "");
  clearTimeout(toast._t); toast._t = setTimeout(() => (t.className = "toast"), 2600);
}

/* ------------------------------------------------------------------ state */
const S = {
  st: null, robots: [], people: [], scene: { places: [], objects: [] }, sel: null, target: "auto",
  layers: { grid: true, objects: true, places: true, paths: true, people: true },
  picking: false, follow: false, mapImg: null, mapMeta: null, mapVer: -1,
  view: { cx: 0, cy: 0, k: 60 }, fitted: false, disp: {}, hist: {}, logs: [], logTab: "app",
  sceneLoaded: false, connected: false, lastMsgAt: 0, busyAll: false,
};

/* ------------------------------------------------------------------ websocket */
function connectWS() {
  const ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws" + (TOKEN ? "?token=" + TOKEN : ""));
  ws.onopen = () => { S.connected = true; };
  ws.onclose = () => { S.connected = false; setPill("#pillLink", "bad"); setTimeout(connectWS, 1000); };
  ws.onmessage = (e) => {
    let st;
    try { st = JSON.parse(e.data.replace(/\bNaN\b|-?\bInfinity\b/g, "null")); } catch (err) { console.error(err); return; }
    onState(st);
  };
}

function setPill(sel, cls) { const p = $(sel); p.className = "pill " + (cls || ""); }
function setProc(sel, cls, info) {
  const p = $(sel); p.className = "proc " + (cls || "");
  if (info !== undefined) p.querySelector("small").textContent = info;
}

function fmtUp(s) { s = Math.round(s); return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m${String(s % 60).padStart(2, "0")}`; }

function onState(st) {
  S.st = st; S.lastMsgAt = performance.now(); S.dirty = true;
  setPill("#pillLink", "ok");
  const real = st.mode === "real";
  $("#modeChip").textContent = real ? "ROBOT THẬT" : "MÔ PHỎNG";
  $("#modeChip").classList.toggle("real", real);

  // --- tien trinh
  const sim = st.procs.sim, llm = st.procs.llm, a = st.assistant;
  const simOn = sim.running || sim.external;
  setProc("#procSim", sim.running ? (a.ready ? "ok" : "wait") : sim.external ? "ok" : "",
    sim.running ? `${sim.args.robots} con · ${fmtUp(sim.uptime)}` : sim.external ? "đang chạy ngoài app" : "đang tắt");
  $("#simBtn").textContent = sim.running ? "Tắt" : "Bật";
  $("#simBtn").classList.toggle("danger", sim.running);
  $("#simBtn").disabled = sim.external && !sim.running;
  setPill("#pillSim", simOn ? (a.ready ? "ok" : "wait") : "");
  if (real) $("#procSim").classList.add("hidden");

  const llmOn = llm.healthy;
  setProc("#procLlm", llmOn ? "ok" : (llm.running ? "wait" : ""),
    llmOn ? (llm.args.model || "đang chạy") : llm.running ? "đang nạp model…" : "đang tắt");
  $("#llmBtn").textContent = llm.running ? "Tắt" : "Bật";
  $("#llmBtn").classList.toggle("danger", llm.running);
  $("#llmBtn").disabled = !llm.running && llm.healthy;
  setPill("#pillLlm", llmOn ? "ok" : llm.running ? "wait" : "");

  const mv = st.procs.movers || {};
  setProc("#procMovers", mv.running ? "ok" : mv.external ? "ok" : "",
    mv.running ? `${mv.args.n} người${mv.args.carts ? " + 3 xe" : ""} đang đi` : mv.external ? "đang chạy ngoài app" : "đứng yên");
  $("#moversBtn").textContent = mv.running || mv.external ? "Tắt" : "Bật";
  $("#moversBtn").classList.toggle("danger", !!(mv.running || mv.external));
  $("#moversBtn").disabled = !(sim.running || sim.external);
  if (sim.running && sim.args.world && document.activeElement !== $("#simWorld")) $("#simWorld").value = sim.args.world;
  $("#simWorld").disabled = sim.running || sim.external;
  const wNow = st.procs.world, wA = a.world;
  const mismatch = a.ready && wNow && wA && wNow !== wA;
  $("#banner").classList.toggle("hidden", !mismatch);
  if (mismatch) $("#bannerTxt").textContent = `Sim đang chạy “${wNow}”, trợ lý còn nạp “${wA}”.`;
  if (a.world && S.world !== a.world) { S.world = a.world; S.sceneLoaded = false; S.fitted = false; S.mapImg = null; }
  if (a.controller) $$("#ctrlSeg button").forEach((b) => b.classList.toggle("on", b.dataset.c === a.controller));

  const ready = a.ready;
  setProc("#procAsst", ready ? "ok" : (/đang|chưa thấy/.test(a.status) ? "wait" : (/lỗi|không/.test(a.status) ? "bad" : "")), a.status);
  $("#asstBtn").disabled = ready || /đang/.test(a.status);
  $("#asstBtn").textContent = ready ? "Đã nối" : "Kết nối";
  setPill("#pillAsst", ready ? "ok" : /đang/.test(a.status) ? "wait" : "");
  $("#cmd").disabled = !ready; $("#send").disabled = !ready; $("#mic").disabled = !ready;
  $("#cmd").placeholder = ready ? "Nhập lệnh… (Enter để gửi, / để gõ nhanh)" : "Kết nối trợ lý trước…";
  $$("#quick button").forEach((b) => (b.disabled = !ready));
  if (ready) {
    $("#mic").classList.toggle("on", !!a.voice);
    if (document.activeElement !== $("#tts")) $("#tts").checked = !!a.tts;
    if (document.activeElement !== $("#wake") && !$("#wake").dataset.dirty) $("#wake").value = (a.wake || []).join(", ");
  }
  $("#splash").classList.toggle("hidden", ready || S.busyAll || simOn);

  // --- robot
  S.robots = st.robots; S.people = st.people;
  if (S.sel === null && S.robots.length) S.sel = S.robots[0].key;
  renderFleet(); renderTarget();
  if (ready && !S.sceneLoaded) loadScene();

  // --- ban do
  if (st.map && st.map.ver !== S.mapVer && st.map.meta) {
    S.mapVer = st.map.ver; S.mapMeta = st.map.meta;
    const img = new Image();
    img.onload = () => { S.mapImg = img; S.dirty = true; };
    img.src = "/api/map.png?v=" + st.map.ver + (TOKEN ? "&token=" + TOKEN : "");
  }

  $("#mapName").textContent = st.map && st.map.name ? "🗺 " + st.map.name : "";
  // --- he thong
  renderSys(st.sys || {});
  // --- nhat ky / chat
  for (const l of st.feed) handleLine(l);
}

/* ------------------------------------------------------------------ fleet */
function robotColor(r) { return RCOL[r.i % RCOL.length]; }
function stateBadge(state, busy) {
  if (/phanh|nhường|kẹt|lùi/.test(state)) return ["warn", "đang tránh"];
  if (busy || /đi|xoay|vòng/.test(state)) return ["go", "đang chạy"];
  return ["", "chờ lệnh"];
}
function renderFleet() {
  const el = $("#fleet");
  $("#fleetCount").textContent = S.robots.length ? `${S.robots.length} con` : "0";
  if (!S.robots.length) {
    if (!el.querySelector(".empty")) el.innerHTML = '<div class="empty">Chưa có robot. Bấm “Chạy tất cả”.</div>';
    return;
  }
  const keys = S.robots.map((r) => r.key).join("|");
  if (el.dataset.keys !== keys) {
    el.dataset.keys = keys;
    el.innerHTML = S.robots.map((r) => `
      <div class="robot" data-key="${r.key}" style="--c:${robotColor(r)}">
        <div class="robot-h"><b>${r.label}</b><span class="badge"></span></div>
        <div class="robot-state"></div>
        <div class="robot-grid">
          <div><span>x</span><b class="vx">—</b></div>
          <div><span>y</span><b class="vy">—</b></div>
          <div><span>hướng</span><b class="vh">—</b></div>
        </div>
        <div class="radar" title="Khoảng trống phía trước"><i></i></div>
      </div>`).join("");
    el.querySelectorAll(".robot").forEach((c) => c.addEventListener("click", () => {
      S.sel = c.dataset.key; renderFleet(); renderTarget();
      if (S.robots.length > 1) { S.target = c.dataset.key; renderTarget(); }
    }));
  }
  for (const r of S.robots) {
    const c = el.querySelector(`.robot[data-key="${CSS.escape(r.key)}"]`);
    if (!c) continue;
    c.classList.toggle("sel", r.key === S.sel);
    const [cls, txt] = stateBadge(r.state || "", r.busy);
    const b = c.querySelector(".badge"); b.className = "badge " + cls; b.textContent = txt;
    c.querySelector(".robot-state").textContent = r.state || "";
    if (r.pose) {
      c.querySelector(".vx").textContent = r.pose[0].toFixed(2);
      c.querySelector(".vy").textContent = r.pose[1].toFixed(2);
      c.querySelector(".vh").textContent = Math.round(r.pose[2] * 180 / Math.PI) + "°";
    }
    const f = r.free == null ? 0 : Math.max(0, Math.min(1, r.free / 3));
    const bar = c.querySelector(".radar i");
    bar.style.width = (f * 100).toFixed(0) + "%";
    bar.style.background = r.free == null ? "var(--dim)" : r.free < 0.4 ? "var(--bad)" : r.free < 1 ? "var(--warn)" : "var(--ok)";
    c.querySelector(".radar").title = r.free == null ? "" : `Trống phía trước: ${r.free.toFixed(2)} m`;
  }
}

function renderTarget() {
  const seg = $("#target");
  if (S.robots.length <= 1) { seg.innerHTML = ""; S.target = "auto"; return; }
  const opts = [["auto", "tự động"], ...S.robots.map((r) => [r.key, r.label]), ["all", "tất cả"]];
  const sig = opts.map((o) => o[0]).join("|");
  if (seg.dataset.sig !== sig) {
    seg.dataset.sig = sig;
    seg.innerHTML = opts.map(([k, l]) => `<button data-k="${k}">${l}</button>`).join("");
    seg.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => { S.target = b.dataset.k; renderTarget(); }));
  }
  seg.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.k === S.target));
}

function prefix() {
  if (S.robots.length <= 1 || S.target === "auto") return "";
  if (S.target === "all") return S.robots.length === 2 ? "cả hai " : "tất cả ";
  const r = S.robots.find((x) => x.key === S.target);
  return r ? r.label + " " : "";
}

/* ------------------------------------------------------------------ scene lists */
async function loadScene() {
  S.sceneLoaded = true;
  try { S.scene = await api("/api/scene"); } catch (e) { S.sceneLoaded = false; return; }
  renderLists();
  if (!S.fitted) fitView();
}
function renderLists() {
  const q = $("#search").value.trim().toLowerCase();
  const pl = S.scene.places.filter((p) => !q || p.name.toLowerCase().includes(q));
  $("#placeList").innerHTML = pl.map((p) => `
    <div class="item" data-say="đi tới ${p.name}" data-x="${p.x}" data-y="${p.y}">
      <span class="pin">◆</span><span class="t">${p.name}</span><span class="go">đi tới →</span></div>`).join("")
    || '<div class="empty">Không có địa điểm.</div>';
  const ob = S.scene.objects.filter((o) => !q || o.desc.toLowerCase().includes(q));
  $("#objList").innerHTML = ob.map((o) => `
    <div class="item" data-say="đi tới ${o.desc}" data-x="${o.x}" data-y="${o.y}">
      <span class="sw" style="background:${OBJ_RGB[o.color] || "#888"}"></span><span class="t">${o.desc}</span><span class="go">đi tới →</span></div>`).join("")
    || '<div class="empty">Không có đồ vật.</div>';
  $$(".list .item").forEach((it) => {
    it.addEventListener("click", () => sendCmd(prefix() + it.dataset.say));
    it.addEventListener("mouseenter", () => (S.hover = [+it.dataset.x, +it.dataset.y]));
    it.addEventListener("mouseleave", () => (S.hover = null));
  });
}

/* ------------------------------------------------------------------ chat */
function chatAdd(node) {
  const c = $("#chat");
  const stick = c.scrollHeight - c.scrollTop - c.clientHeight < 60;
  c.appendChild(node);
  while (c.children.length > 300) c.removeChild(c.children[1]);
  if (stick) c.scrollTop = c.scrollHeight;
}
function el(cls, text) { const d = document.createElement("div"); d.className = cls; d.textContent = text; return d; }
let lastBot = null;
function handleLine(l) {
  S.logs.push(l); if (S.logs.length > 1500) S.logs.shift();
  if (!$("#drawer").classList.contains("hidden") && S.logTab === "app") appendLog(l);
  const t = l.text.trim();
  if (l.src === "sys") { chatAdd(el("ev sys", t)); return; }
  let m;
  if ((m = t.match(/^Bạn:\s*(.*)$/))) { if (m[1]) chatAdd(el("msg me", m[1])); return; }
  if ((m = t.match(/^🗣️?\s*Nghe:\s*(.*)$/u))) { chatAdd(el("msg voice", m[1])); return; }
  if ((m = t.match(/^🐶\s*Gô:\s*(.*?)\s*(?:\[([^\]]+)\])?$/u))) {
    const b = el("msg bot", m[1]);
    if (m[2]) { const meta = document.createElement("div"); meta.className = "meta"; meta.innerHTML = `<i>${m[2]}</i>`; b.appendChild(meta); }
    chatAdd(b); lastBot = b; return;
  }
  if ((m = t.match(/⏱️?\s*STT\s*(\d+).*?=\s*(\d+)ms/u))) {
    if (lastBot) {
      let meta = lastBot.querySelector(".meta");
      if (!meta) { meta = document.createElement("div"); meta.className = "meta"; lastBot.appendChild(meta); }
      const i = document.createElement("i"); i.textContent = `${m[2]} ms` + (+m[1] ? ` (nghe ${m[1]} ms)` : ""); meta.appendChild(i);
    }
    return;
  }
  if (t.includes("✅")) { chatAdd(el("ev ok", t.replace(/^\[[^\]]+\]\s*✅\s*/, "✓ ").replace(/✅\s*/, "✓ "))); return; }
  if (t.includes("🛑")) { chatAdd(el("ev bad", t.replace(/^\[[^\]]+\]\s*/, ""))); return; }
  if (t.includes("📢")) { chatAdd(el("ev", t.replace(/^📢\s*/, ""))); return; }
  if (t.includes("🧹")) { chatAdd(el("ev warn", "Đã chặn: " + t.replace(/^.*?bỏ:\s*/, ""))); return; }
  if (t.includes("🔇")) { chatAdd(el("ev sys", t.replace(/^🔇\s*/, ""))); return; }
  if (/^\[voice\]/.test(t)) { chatAdd(el("ev sys", t.replace(/^\[voice\]\s*/, "Mic: "))); return; }
  if (/⚠️|Traceback|Error|loi/.test(t) && !/throttled/.test(t)) {
    if (/Traceback|Error/.test(t)) chatAdd(el("ev bad", t.slice(0, 160)));
  }
}

async function sendCmd(text) {
  text = (text || "").trim();
  if (!text) return;
  try {
    const r = await api("/api/say", { text });
    if (!r || !r.ok) toast("Trợ lý chưa sẵn sàng", true);
  } catch (e) { toast("Không gửi được lệnh", true); }
}

/* ------------------------------------------------------------------ he thong */
const SYS_KEYS = { cpu: ["cpu", "%"], ram: ["ram", "%"], gpu: ["gpu", "%"], vram: ["vram", "%"] };
function renderSys(s) {
  for (const m of $$(".meter")) {
    const k = m.dataset.k, [key, unit] = SYS_KEYS[k];
    const v = s[key];
    const h = (S.hist[k] = S.hist[k] || []);
    if (v != null && (!h.t || performance.now() - h.t > 900)) { h.push(v); h.t = performance.now(); if (h.length > 60) h.shift(); }
    let txt = v == null ? "—" : Math.round(v) + unit;
    if (k === "cpu" && s.temp != null) txt += ` · ${s.temp}°`;
    if (k === "gpu" && s.gpu_temp != null) txt += ` · ${s.gpu_temp}°`;
    if (k === "ram" && s.ram_gb != null) txt += ` · ${s.ram_gb}G`;
    if (k === "vram" && s.vram_gb != null) txt += ` · ${s.vram_gb}G`;
    m.querySelector("b").textContent = txt;
    spark(m.querySelector("canvas"), h, 100);
  }
}
function spark(cv, data, max) {
  const dpr = devicePixelRatio || 1, w = cv.clientWidth, h = cv.clientHeight;
  if (cv.width !== w * dpr) { cv.width = w * dpr; cv.height = h * dpr; }
  const g = cv.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, w, h);
  if (data.length < 2) return;
  const last = data[data.length - 1];
  const col = last > 85 ? "#f85149" : last > 65 ? "#d29922" : "#3ea6ff";
  g.beginPath();
  data.forEach((v, i) => { const x = (i / 59) * w, y = h - 2 - (Math.min(v, max) / max) * (h - 4); i ? g.lineTo(x, y) : g.moveTo(x, y); });
  g.strokeStyle = col; g.lineWidth = 1.5; g.stroke();
  g.lineTo(((data.length - 1) / 59) * w, h); g.lineTo(0, h); g.closePath();
  const grd = g.createLinearGradient(0, 0, 0, h); grd.addColorStop(0, col + "55"); grd.addColorStop(1, col + "00");
  g.fillStyle = grd; g.fill();
}

/* ------------------------------------------------------------------ ban do */
const cv = $("#map"), ctx = cv.getContext("2d");
function W2S(x, y) { const v = S.view; return [cv.clientWidth / 2 + (x - v.cx) * v.k, cv.clientHeight / 2 - (y - v.cy) * v.k]; }
function S2W(px, py) { const v = S.view; return [v.cx + (px - cv.clientWidth / 2) / v.k, v.cy - (py - cv.clientHeight / 2) / v.k]; }

function fitView() {
  const pts = [...S.scene.objects.map((o) => [o.x, o.y]), ...S.scene.places.map((p) => [p.x, p.y]),
    ...S.robots.filter((r) => r.pose).map((r) => r.pose)];
  if (S.mapMeta && !pts.length) { const m = S.mapMeta; pts.push([m.x0, m.y0], [m.x0 + m.nx * m.res, m.y0 + m.ny * m.res]); }
  if (!pts.length) return;
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const [x, y] of pts) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
  const pad = 1.2;
  S.view.cx = (x0 + x1) / 2; S.view.cy = (y0 + y1) / 2;
  S.view.k = Math.max(15, Math.min(cv.clientWidth / (x1 - x0 + 2 * pad), cv.clientHeight / (y1 - y0 + 2 * pad)));
  S.fitted = true; S.dirty = true;
}

function lerpAng(a, b, t) { let d = b - a; while (d > Math.PI) d -= 2 * Math.PI; while (d < -Math.PI) d += 2 * Math.PI; return a + d * t; }

/* Ve THEO NHU CAU: chi khi co goi trang thai moi, khi keo/zoom, hoac khi dang co hieu ung
   (quy dao chay, robot dang truot toi vi tri moi). Toi da 30 hinh/giay. Dung yen = ~0 % CPU. */
let lastDraw = 0;
function needAnim() {
  if (S.hover || S.follow || S.aim) return true;
  for (const r of S.robots) {
    if (r.goal) return true;
    const d = S.disp[r.key];
    if (r.pose && d && (Math.abs(r.pose[0] - d[0]) > 0.003 || Math.abs(r.pose[1] - d[1]) > 0.003)) return true;
  }
  return false;
}
function tick(now) {
  requestAnimationFrame(tick);
  if (document.hidden) return;
  if (!S.dirty && !needAnim()) return;
  if (now - lastDraw < 33) return;
  lastDraw = now; S.dirty = false;
  draw();
}
function draw() {
  const dpr = devicePixelRatio || 1, w = cv.clientWidth, h = cv.clientHeight;
  if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  const k = S.view.k;

  // luoi 1 m
  const [wx0, wy1] = S2W(0, 0), [wx1, wy0] = S2W(w, h);
  const step = k < 25 ? 2 : k < 120 ? 1 : 0.5;
  ctx.lineWidth = 1;
  for (let x = Math.floor(wx0 / step) * step; x <= wx1; x += step) {
    const [px] = W2S(x, 0); ctx.strokeStyle = Math.abs(x) < 1e-6 ? "#1f3347" : "#121c26";
    ctx.beginPath(); ctx.moveTo(Math.round(px) + .5, 0); ctx.lineTo(Math.round(px) + .5, h); ctx.stroke();
  }
  for (let y = Math.floor(wy0 / step) * step; y <= wy1; y += step) {
    const [, py] = W2S(0, y); ctx.strokeStyle = Math.abs(y) < 1e-6 ? "#1f3347" : "#121c26";
    ctx.beginPath(); ctx.moveTo(0, Math.round(py) + .5); ctx.lineTo(w, Math.round(py) + .5); ctx.stroke();
  }

  // ban do robot tu ve
  if (S.layers.grid && S.mapImg && S.mapMeta) {
    const m = S.mapMeta, [px, py] = W2S(m.x0, m.y0 + m.ny * m.res);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(S.mapImg, px, py, m.nx * m.res * k, m.ny * m.res * k);
  }

  // do vat
  if (S.layers.objects) {
    for (const o of S.scene.objects) {
      const [px, py] = W2S(o.x, o.y);
      ctx.save(); ctx.translate(px, py); ctx.rotate(-o.yaw);
      const c = OBJ_RGB[o.color] || "#888";
      ctx.fillStyle = c + "40"; ctx.strokeStyle = c + "cc"; ctx.lineWidth = 1.2;
      ctx.beginPath(); roundRect(ctx, -o.sx * k / 2, -o.sy * k / 2, o.sx * k, o.sy * k, 3); ctx.fill(); ctx.stroke();
      ctx.restore();
      if (k > 38) label(o.desc, px, py, "#c9d4df", 10.5);
    }
  }
  // dia diem
  if (S.layers.places) {
    for (const p of S.scene.places) {
      const [px, py] = W2S(p.x, p.y);
      ctx.fillStyle = "#3ea6ff"; ctx.beginPath();
      ctx.moveTo(px, py - 6); ctx.lineTo(px + 5, py); ctx.lineTo(px, py + 6); ctx.lineTo(px - 5, py); ctx.closePath(); ctx.fill();
      if (k > 30) label(p.name, px, py - 13, "#9fd2ff", 11, true);
    }
  }
  // hover tu danh sach
  if (S.hover) {
    const [px, py] = W2S(S.hover[0], S.hover[1]); const r = 14 + 4 * Math.sin(performance.now() / 180);
    ctx.strokeStyle = "#3ea6ffcc"; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(px, py, r, 0, 7); ctx.stroke();
  }

  // quy dao + dich
  const now = performance.now();
  for (const r of S.robots) {
    const col = robotColor(r);
    if (S.layers.paths && r.path && r.path.length > 1) {
      ctx.setLineDash([7, 6]); ctx.lineDashOffset = -now / 40; ctx.strokeStyle = col; ctx.lineWidth = 2.2;
      ctx.beginPath(); r.path.forEach(([x, y], i) => { const [px, py] = W2S(x, y); i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); }); ctx.stroke();
      ctx.setLineDash([]);
    }
    if (S.layers.paths && r.local && r.local.length > 1) {
      ctx.strokeStyle = "#ffffffcc"; ctx.lineWidth = 3; ctx.lineCap = "round";
      ctx.beginPath(); r.local.forEach(([x, y], i) => { const [px, py] = W2S(x, y); i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); }); ctx.stroke();
      ctx.strokeStyle = col; ctx.lineWidth = 1.6; ctx.stroke(); ctx.lineCap = "butt";
    }
    if (r.goal) {
      const [gx, gy] = W2S(r.goal[0], r.goal[1]); const pr = 0.5 + 0.5 * Math.sin(now / 250);
      ctx.strokeStyle = col; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(gx, gy, 8 + 6 * pr, 0, 7); ctx.stroke();
      ctx.fillStyle = col; ctx.beginPath(); ctx.arc(gx, gy, 4, 0, 7); ctx.fill();
    }
  }
  // lo trinh dang chuan bi (Shift+bam)
  if (S.route.length) {
    ctx.strokeStyle = "#7c5cff"; ctx.lineWidth = 2; ctx.setLineDash([4, 4]);
    const sel = S.robots.find((r) => r.key === selNs());
    ctx.beginPath();
    if (sel && S.disp[sel.key]) { const [px, py] = W2S(S.disp[sel.key][0], S.disp[sel.key][1]); ctx.moveTo(px, py); }
    S.route.forEach(([x, y], i) => { const [px, py] = W2S(x, y); (i || sel) ? ctx.lineTo(px, py) : ctx.moveTo(px, py); });
    ctx.stroke(); ctx.setLineDash([]);
    S.route.forEach(([x, y], i) => {
      const [px, py] = W2S(x, y);
      ctx.fillStyle = "#7c5cff"; ctx.beginPath(); ctx.arc(px, py, 10, 0, 7); ctx.fill();
      ctx.fillStyle = "#fff"; ctx.font = "600 11px Inter, system-ui"; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(String(i + 1), px, py + 0.5);
    });
  }
  // diem dang chon (hop popup)
  if (S.pop) {
    const [px, py] = W2S(S.pop.x, S.pop.y);
    ctx.strokeStyle = "#3ea6ff"; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(px, py, 9, 0, 7); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(px - 15, py); ctx.lineTo(px - 5, py); ctx.moveTo(px + 5, py); ctx.lineTo(px + 15, py);
    ctx.moveTo(px, py - 15); ctx.lineTo(px, py - 5); ctx.moveTo(px, py + 5); ctx.lineTo(px, py + 15); ctx.stroke();
    ctx.fillStyle = "#3ea6ff22"; ctx.beginPath(); ctx.arc(px, py, 0.22 * k, 0, 7); ctx.fill();
  }
  // cham nhanh: dang keo chon huong
  if (S.aim) {
    const [px, py] = W2S(S.aim.x, S.aim.y), [qx, qy] = W2S(S.aim.ex, S.aim.ey);
    ctx.fillStyle = "#3ea6ff"; ctx.beginPath(); ctx.arc(px, py, 6, 0, 7); ctx.fill();
    if (Math.hypot(qx - px, qy - py) > 0.25 * k) arrow(px, py, qx, qy, "#3ea6ff");
  }
  // nguoi
  if (S.layers.people) {
    for (const p of S.people) {
      const [px, py] = W2S(p.x, p.y);
      ctx.fillStyle = "#ff5a5233"; ctx.beginPath(); ctx.arc(px, py, 0.6 * k, 0, 7); ctx.fill();
      ctx.fillStyle = "#ff5a52"; ctx.beginPath(); ctx.arc(px, py, Math.max(4, 0.22 * k), 0, 7); ctx.fill();
      const sp = Math.hypot(p.vx, p.vy);
      if (sp > 0.05) {
        const [qx, qy] = W2S(p.x + p.vx * 1.2, p.y + p.vy * 1.2);
        arrow(px, py, qx, qy, "#ff8d86");
      }
    }
  }
  // robot (noi suy giua cac goi 5 Hz cho muot)
  for (const r of S.robots) {
    if (!r.pose) continue;
    const d = (S.disp[r.key] = S.disp[r.key] || r.pose.slice());
    d[0] += (r.pose[0] - d[0]) * 0.25; d[1] += (r.pose[1] - d[1]) * 0.25; d[2] = lerpAng(d[2], r.pose[2], 0.25);
    const col = robotColor(r), [px, py] = W2S(d[0], d[1]);
    ctx.save(); ctx.translate(px, py); ctx.rotate(-d[2]);
    const L = 0.70 * k, Wd = 0.31 * k;
    if (r.key === S.sel) { ctx.strokeStyle = col + "66"; ctx.lineWidth = 6; ctx.beginPath(); roundRect(ctx, -L / 2 - 4, -Wd / 2 - 4, L + 8, Wd + 8, 7); ctx.stroke(); }
    ctx.fillStyle = col + "dd"; ctx.strokeStyle = "#0a0e13"; ctx.lineWidth = 1.5;
    ctx.beginPath(); roundRect(ctx, -L / 2, -Wd / 2, L, Wd, Math.min(6, Wd / 3)); ctx.fill(); ctx.stroke();
    ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.moveTo(L / 2 + 2, 0); ctx.lineTo(L / 2 - Math.min(10, L / 4), -Wd / 3); ctx.lineTo(L / 2 - Math.min(10, L / 4), Wd / 3); ctx.closePath(); ctx.fill();
    ctx.restore();
    label(r.label + (r.state && r.state !== "chờ lệnh" ? " · " + r.state : ""), px, py - Math.max(16, 0.45 * k), "#fff", 11.5, true, col);
  }
  placePop();
  if (S.follow) { const r = S.robots.find((x) => x.key === S.sel); if (r && S.disp[r.key]) { S.view.cx += (S.disp[r.key][0] - S.view.cx) * 0.1; S.view.cy += (S.disp[r.key][1] - S.view.cy) * 0.1; } }

  // thuoc ty le
  let m = 1; const targetPx = 70;
  for (const c of [0.25, 0.5, 1, 2, 5, 10]) { m = c; if (c * k >= targetPx * 0.6) break; }
  $("#scaleBar").style.width = Math.round(m * k) + "px"; $("#scaleTxt").textContent = m + " m";

}
setInterval(() => { if (S.connected && performance.now() - S.lastMsgAt > 3000) setPill("#pillLink", "wait"); }, 1000);
window.addEventListener("resize", () => (S.dirty = true));
function roundRect(g, x, y, w, h, r) { g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }
function label(t, x, y, col, size, bold, bg) {
  ctx.font = `${bold ? 600 : 400} ${size}px Inter, system-ui, sans-serif`;
  const w = ctx.measureText(t).width;
  ctx.fillStyle = bg ? bg + "e6" : "rgba(10,14,19,.75)";
  ctx.beginPath(); roundRect(ctx, x - w / 2 - 5, y - size / 2 - 4, w + 10, size + 8, 5); ctx.fill();
  ctx.fillStyle = bg ? "#04121f" : col; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(t, x, y + 0.5);
}
function arrow(x0, y0, x1, y1, col) {
  ctx.strokeStyle = col; ctx.fillStyle = col; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
  const a = Math.atan2(y1 - y0, x1 - x0); ctx.beginPath(); ctx.moveTo(x1, y1);
  ctx.lineTo(x1 - 8 * Math.cos(a - 0.45), y1 - 8 * Math.sin(a - 0.45)); ctx.lineTo(x1 - 8 * Math.cos(a + 0.45), y1 - 8 * Math.sin(a + 0.45)); ctx.closePath(); ctx.fill();
}

/* tuong tac ban do:
   bam 1 lan  -> hop "Đi tới đây / + Lộ trình / Đặt tên" (an toan: khong di nham khi bam lo)
   bam dup    -> di luon
   Shift+bam  -> them diem vao lo trinh (di lan luot, hoac tuan tra)
   Cham nhanh (G): bam = di ngay, bam-KEO = di + quay mat theo huong keo (nhu 2D Goal Pose RViz)
   keo nen = di chuyen ban do, lan chuot = zoom */
let drag = null;
S.route = []; S.pop = null; S.aim = null;
function evWorld(e) { const r = cv.getBoundingClientRect(); return S2W(e.clientX - r.left, e.clientY - r.top); }
function selNs() { return S.target !== "auto" && S.target !== "all" ? S.target : S.sel; }

cv.addEventListener("mousedown", (e) => {
  if (e.button !== 0) return;
  const [wx, wy] = evWorld(e);
  if (S.picking) { S.aim = { x: wx, y: wy, ex: wx, ey: wy }; S.dirty = true; return; }
  drag = { x: e.clientX, y: e.clientY, cx: S.view.cx, cy: S.view.cy, moved: false };
});
window.addEventListener("mouseup", (e) => {
  if (S.aim) {
    const a = S.aim; S.aim = null; S.dirty = true;
    const yaw = Math.hypot(a.ex - a.x, a.ey - a.y) > 0.25 ? Math.atan2(a.ey - a.y, a.ex - a.x) : null;
    gotoPoint(a.x, a.y, yaw);
    return;
  }
  if (!drag) return;
  const d = drag; drag = null; cv.classList.remove("drag");
  if (d.moved || e.target !== cv) return;
  const [wx, wy] = evWorld(e);
  let best = null, bd = 0.45;
  for (const r of S.robots) if (r.pose) { const dd = Math.hypot(r.pose[0] - wx, r.pose[1] - wy); if (dd < bd) { bd = dd; best = r; } }
  if (best) { S.sel = best.key; renderFleet(); hidePop(); return; }
  if (e.shiftKey) { addRoute(wx, wy); return; }
  showPop(wx, wy);
});
cv.addEventListener("dblclick", (e) => { const [wx, wy] = evWorld(e); hidePop(); gotoPoint(wx, wy, null); });
window.addEventListener("mousemove", (e) => {
  const rect = cv.getBoundingClientRect();
  if (e.target === cv) { const [wx, wy] = S2W(e.clientX - rect.left, e.clientY - rect.top); $("#cursor").textContent = `x ${wx.toFixed(2)}, y ${wy.toFixed(2)}`; }
  if (S.aim) { const [wx, wy] = S2W(e.clientX - rect.left, e.clientY - rect.top); S.aim.ex = wx; S.aim.ey = wy; S.dirty = true; return; }
  if (!drag) return;
  const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
  if (Math.abs(dx) + Math.abs(dy) > 3) { drag.moved = true; cv.classList.add("drag"); S.follow = false; $("#follow").classList.remove("on"); }
  S.view.cx = drag.cx - dx / S.view.k; S.view.cy = drag.cy + dy / S.view.k; S.dirty = true;
});
cv.addEventListener("wheel", (e) => {
  e.preventDefault();
  const rect = cv.getBoundingClientRect(), mx = e.clientX - rect.left, my = e.clientY - rect.top;
  const [wx, wy] = S2W(mx, my);
  S.view.k = Math.max(8, Math.min(400, S.view.k * Math.exp(-e.deltaY * 0.0015)));
  const [nx, ny] = S2W(mx, my); S.view.cx += wx - nx; S.view.cy += wy - ny; S.dirty = true;
}, { passive: false });
function setPicking(on) {
  S.picking = on; $("#pickGoal").classList.toggle("on", on); cv.classList.toggle("picking", on);
  const h = $("#maphint"); h.textContent = "Chấm nhanh: bấm = đi tới · bấm rồi KÉO = chọn hướng robot quay mặt · G để tắt";
  h.classList.toggle("on", on); if (on) hidePop();
}

async function gotoPoint(x, y, yaw, name) {
  hidePop();
  if (!S.st || !S.st.assistant.ready) return toast("Kết nối trợ lý trước", true);
  try {
    const r = await api("/api/goto_xy", { ns: selNs(), x, y, yaw, name });
    if (r && r.ok) toast(`Đi tới (${x.toFixed(1)}, ${y.toFixed(1)})` + (yaw != null ? `, quay ${Math.round(yaw * 180 / Math.PI)}°` : "")
      + (r.msg && r.msg.startsWith("Chưa quét") ? " · chưa quét chỗ này, robot vừa đi vừa dò" : ""));
    else toast(r ? r.msg : "Không gửi được", true);
  } catch (e) { toast("Không gửi được", true); }
}
const ST_TXT = { free: "trống", unknown: "chưa quét", wall: "vật cản", outside: "ngoài bản đồ" };
async function showPop(x, y) {
  S.pop = { x, y }; S.dirty = true;
  $("#popXY").textContent = `x ${x.toFixed(2)}, y ${y.toFixed(2)}`;
  const st = $("#popState"); st.className = "st"; st.textContent = "…";
  $("#popNameRow").classList.add("hidden");
  $("#popGo").disabled = $("#popRoute").disabled = false;
  $("#pop").classList.remove("hidden"); placePop();
  try {
    const c = await api(`/api/check?x=${x}&y=${y}`);
    if (S.pop && S.pop.x === x) {
      st.className = "st " + c.state; st.textContent = ST_TXT[c.state] || c.state; st.title = c.msg;
      $("#popGo").disabled = $("#popRoute").disabled = !c.ok;
      $("#popGo").textContent = c.ok ? "▶ Đi tới đây" : ({ wall: "✕ Có vật cản", outside: "✕ Ngoài bản đồ" }[c.state] || "✕ Không đi được");
      $("#popGo").title = c.msg;
    }
  } catch (e) { /* van cho di: backend se kiem tra lai */ }
}
function hidePop() { if (!S.pop) return; S.pop = null; $("#pop").classList.add("hidden"); $("#popGo").textContent = "▶ Đi tới đây"; S.dirty = true; }
function placePop() {
  if (!S.pop) return;
  const [px, py] = W2S(S.pop.x, S.pop.y), p = $("#pop"), W = cv.clientWidth, H = cv.clientHeight;
  let l = px + 16, t = py - 34;
  if (l + 224 > W) l = px - 230;
  if (t + p.offsetHeight > H - 8) t = H - 8 - p.offsetHeight;
  if (t < 48) t = 48;
  p.style.left = Math.max(8, l) + "px"; p.style.top = t + "px";
}
$("#popGo").addEventListener("click", () => S.pop && gotoPoint(S.pop.x, S.pop.y, null));
$("#popRoute").addEventListener("click", () => { if (S.pop) { addRoute(S.pop.x, S.pop.y); hidePop(); } });
$("#popName").addEventListener("click", () => { $("#popNameRow").classList.toggle("hidden"); $("#popNameIn").focus(); placePop(); });
$("#popNameOk").addEventListener("click", savePlace);
$("#popNameIn").addEventListener("keydown", (e) => { if (e.key === "Enter") savePlace(); });
async function savePlace() {
  if (!S.pop) return;
  const name = $("#popNameIn").value.trim(); if (!name) return;
  const r = await api("/api/place", { name, x: S.pop.x, y: S.pop.y });
  toast(r.ok ? `${r.msg} — giờ nói “đi tới ${name}” là robot tới` : r.msg, !r.ok);
  if (r.ok) { $("#popNameIn").value = ""; hidePop(); S.sceneLoaded = false; loadScene(); }
}

function addRoute(x, y) { S.route.push([x, y]); renderRoute(); }
function renderRoute() {
  const n = S.route.length;
  $("#routebar").classList.toggle("hidden", !n);
  $("#routeN").textContent = `Lộ trình: ${n} điểm`; S.dirty = true;
}
async function sendRoute(loop) {
  if (!S.st || !S.st.assistant.ready) return toast("Kết nối trợ lý trước", true);
  const r = await api("/api/route", { ns: selNs(), points: S.route, loop });
  toast(r.msg, !r.ok);
  if (r.ok) { S.route = []; renderRoute(); }
}
$("#routeGo").addEventListener("click", () => sendRoute(false));
$("#routeLoop").addEventListener("click", () => sendRoute(true));
$("#routeUndo").addEventListener("click", () => { S.route.pop(); renderRoute(); });
$("#routeClear").addEventListener("click", () => { S.route = []; renderRoute(); });

/* ban do: luu / mo / quet lai */
$("#mapSave").addEventListener("click", async () => {
  const name = prompt("Đặt tên bản đồ:", "nha_" + new Date().toISOString().slice(0, 10));
  if (name === null) return;
  const r = await api("/api/map/save", { name }); toast(r.msg, !r.ok);
});
$("#mapOpen").addEventListener("click", async (e) => {
  e.stopPropagation();
  const m = $("#mapMenu");
  if (!m.classList.contains("hidden")) { m.classList.add("hidden"); return; }
  const r = await api("/api/maps");
  m.innerHTML = r.maps.length ? r.maps.map((x) => `<button data-n="${x.name}">${x.name}
      <small style="color:var(--dim);float:right">${new Date(x.t * 1000).toLocaleString("vi-VN", { hour12: false })}</small></button>`).join("")
    : '<div class="empty">Chưa lưu bản đồ nào. Quét xong bấm “💾 Lưu bản đồ”.</div>';
  m.classList.remove("hidden");
  m.querySelectorAll("button").forEach((b) => b.addEventListener("click", async () => {
    m.classList.add("hidden"); const rr = await api("/api/map/load", { name: b.dataset.n }); toast(rr.msg, !rr.ok);
  }));
});
document.addEventListener("click", (e) => { if (!e.target.closest(".dd")) $("#mapMenu").classList.add("hidden"); });
$("#mapClear").addEventListener("click", async () => {
  if (!confirm("Xoá bản đồ đã quét và quét lại từ đầu?")) return;
  const r = await api("/api/map/clear", {}); toast(r.msg, !r.ok);
});

/* ------------------------------------------------------------------ dieu khien */
const QUICK = [
  ["Tiến 1 m", "đi thẳng 1 mét"], ["Lùi 0.5 m", "lùi 0.5 mét"], ["↺ 90°", "xoay trái 90 độ"], ["↻ 90°", "xoay phải 90 độ"],
  ["Đứng lên", "đứng lên"], ["Nằm xuống", "nằm xuống"], ["Chào", "chào đi"], ["Ở đâu?", "đang ở đâu"],
];
$("#quick").innerHTML = QUICK.map(([l, c]) => `<button data-c="${c}" disabled>${l}</button>`).join("");
$$("#quick button").forEach((b) => b.addEventListener("click", () => sendCmd(prefix() + b.dataset.c)));

$("#composer").addEventListener("submit", (e) => {
  e.preventDefault();
  const v = $("#cmd").value.trim(); if (!v) return;
  const hasName = /^(con|cả|tất)\b/i.test(v);
  sendCmd((hasName ? "" : prefix()) + v); $("#cmd").value = "";
});
$("#estop").addEventListener("click", estop);
async function estop() {
  $("#estop").classList.add("hit"); setTimeout(() => $("#estop").classList.remove("hit"), 300);
  try { const r = await api("/api/estop", {}); toast(r && r.ok ? "Đã dừng khẩn cấp tất cả robot" : "Trợ lý chưa kết nối", !(r && r.ok)); }
  catch (e) { toast("E-STOP lỗi kết nối!", true); }
}
$("#mic").addEventListener("click", async () => {
  const on = !$("#mic").classList.contains("on");
  $("#mic").classList.toggle("on", on);
  await api("/api/voice", { on }); toast(on ? "Mic đang nghe — cứ nói" : "Đã tắt mic");
});
$("#tts").addEventListener("change", () => api("/api/tts", { on: $("#tts").checked }));
$("#wake").addEventListener("input", () => ($("#wake").dataset.dirty = "1"));
$("#wake").addEventListener("change", async () => {
  delete $("#wake").dataset.dirty;
  await api("/api/wake", { wake: $("#wake").value }); toast($("#wake").value.trim() ? `Chỉ nghe câu có “${$("#wake").value.trim()}”` : "Đã tắt từ đánh thức");
});

$("#simBtn").addEventListener("click", async () => {
  if (S.st && (S.st.procs.sim.running || S.st.procs.sim.external)) { if (!confirm("Tắt mô phỏng? Robot sẽ dừng.")) return; await api("/api/sim/stop", {}); return; }
  const r = await api("/api/sim/start", { robots: +$("#simRobots").value, gui: $("#simGui").checked, world: $("#simWorld").value });
  if (r && r.msg) toast(r.msg, !r.ok);
});
$("#llmBtn").addEventListener("click", async () => {
  if (S.st && S.st.procs.llm.running) { await api("/api/llm/stop", {}); return; }
  const r = await api("/api/llm/start", { model: $("#llmModel").value });
  if (r && r.msg) toast(r.msg, !r.ok);
});
$("#moversBtn").addEventListener("click", async () => {
  const m = S.st && S.st.procs.movers;
  if (m && (m.running || m.external)) { await api("/api/movers/stop", {}); return; }
  const r = await api("/api/movers/start", { n: +$("#moversN").value, carts: true }); toast(r.msg, !r.ok);
});
$$("#ctrlSeg button").forEach((b) => b.addEventListener("click", async () => {
  const r = await api("/api/controller", { name: b.dataset.c });
  toast(r && r.ok ? `Né vật cản: ${b.textContent}` : "Kết nối trợ lý trước", !(r && r.ok));
}));
$("#bannerBtn").addEventListener("click", async () => {
  await api("/api/restart", {}); toast("Đang nạp lại trợ lý cho bản đồ mới…");
  setTimeout(() => api("/api/assistant/connect", { tts: $("#tts").checked, wake: $("#wake").value }).catch(() => {}), 4000);
});
$("#asstBtn").addEventListener("click", () => api("/api/assistant/connect", { tts: $("#tts").checked, wake: $("#wake").value }));

async function runAll() {
  S.busyAll = true; $("#splash").classList.add("hidden");
  const st = S.st;
  try {
    if (st && st.mode !== "real" && !st.procs.sim.running && !st.procs.sim.external)
      await api("/api/sim/start", { robots: +$("#simRobots").value, gui: $("#simGui").checked, world: $("#simWorld").value });
    if (st && !st.procs.llm.running && !st.procs.llm.healthy) await api("/api/llm/start", { model: $("#llmModel").value });
    toast("Đang khởi động… robot đứng dậy sau khoảng 30 giây");
    await new Promise((r) => setTimeout(r, st && st.mode === "real" ? 1000 : 12000));
    await api("/api/assistant/connect", { tts: $("#tts").checked, wake: $("#wake").value });
  } catch (e) { toast("Khởi động lỗi: " + e.message, true); }
  setTimeout(() => (S.busyAll = false), 60000);
}
$("#runAll").addEventListener("click", runAll);
$("#splashRun").addEventListener("click", runAll);

$$(".layer, .maptools .tool[data-layer]").forEach((b) => b.addEventListener("click", () => {
  const l = b.dataset.layer; S.layers[l] = !S.layers[l]; b.classList.toggle("on", S.layers[l]); S.dirty = true;
}));
$("#pickGoal").addEventListener("click", () => setPicking(!S.picking));
$("#follow").addEventListener("click", () => { S.follow = !S.follow; $("#follow").classList.toggle("on", S.follow); });
$("#fit").addEventListener("click", fitView);
$$(".card .tabs .tab").forEach((t) => t.addEventListener("click", () => {
  $$(".card .tabs .tab").forEach((x) => x.classList.toggle("on", x === t));
  $("#placeList").classList.toggle("hidden", t.dataset.tab !== "places");
  $("#objList").classList.toggle("hidden", t.dataset.tab !== "objects");
}));
$("#search").addEventListener("input", renderLists);

/* nhat ky */
function appendLog(l) {
  const v = $("#logview"); const stick = v.scrollHeight - v.scrollTop - v.clientHeight < 40;
  v.textContent += (l.text || l) + "\n"; if (stick) v.scrollTop = v.scrollHeight;
}
async function showLog(tab) {
  S.logTab = tab;
  $$("#drawer .tab").forEach((t) => t.classList.toggle("on", t.dataset.log === tab));
  const v = $("#logview");
  if (tab === "app") v.textContent = S.logs.map((l) => l.text).join("\n") + "\n";
  else { const r = await api("/api/logs/" + tab); v.textContent = (r.lines || []).join("\n") + "\n"; }
  v.scrollTop = v.scrollHeight;
}
$("#logsBtn").addEventListener("click", () => { $("#drawer").classList.remove("hidden"); showLog(S.logTab); });
$("#drawerClose").addEventListener("click", () => $("#drawer").classList.add("hidden"));
$$("#drawer .tab").forEach((t) => t.addEventListener("click", () => showLog(t.dataset.log)));
setInterval(() => { if (!$("#drawer").classList.contains("hidden") && S.logTab !== "app") showLog(S.logTab); }, 2000);

/* phim tat */
window.addEventListener("keydown", (e) => {
  const typing = ["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName);
  if (e.key === "Escape") {          // AN TOAN TRUOC: Esc luon dung robot, dong luon popup
    hidePop(); if (S.picking) setPicking(false); $("#mapMenu").classList.add("hidden");
    estop(); e.preventDefault(); return;
  }
  if (typing) return;
  if (e.key === "/") { $("#cmd").focus(); e.preventDefault(); }
  else if (e.key === "m" || e.key === "M") $("#mic").click();
  else if (e.key === "g" || e.key === "G") setPicking(!S.picking);
  else if (e.key === "f" || e.key === "F") $("#follow").click();
});

setInterval(() => { $("#clock").textContent = new Date().toLocaleTimeString("vi-VN", { hour12: false }); }, 1000);

/* khoi dong */
(async function init() {
  try {
    const info = await api("/api/info");
    $("#llmModel").innerHTML = info.models.map((m) => `<option value="${m.path}">${m.name.replace(/-q4_k_m\.gguf$|\.gguf$/, "")}</option>`).join("")
      || '<option value="">(không có .gguf)</option>';
    if (info.mode === "real") { $("#procSim").classList.add("hidden"); $("#splash small").textContent = "Bộ não LLM → trợ lý trên robot thật."; }
  } catch (e) { toast("Không nối được backend", true); }
  connectWS();
  S.dirty = true;
  requestAnimationFrame(tick);
})();

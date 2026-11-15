/* Quantum Table front page: gameplay only. Plain JS, no build step. */
const $ = (s) => document.querySelector(s);
const api = async (path, body) => {
  const r = await fetch(path, body !== undefined ? { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) } : {});
  if (!r.ok) throw new Error((await r.text()).slice(0, 200));
  return r.json();
};
const params = new URLSearchParams(location.search);
const DEFAULT_3D = true;
let me = JSON.parse(localStorage.getItem("qt_game_me") || "null");
let STATE = null, CHIP = null, rolling = false, lastShown = null;

/* ---------- dice ---------- */
const PIPS = { 1: [4], 2: [0, 8], 3: [0, 4, 8], 4: [0, 2, 6, 8], 5: [0, 2, 4, 6, 8], 6: [0, 2, 3, 5, 6, 8] };
function drawDie(el, face) {
  if (!el) return; el.innerHTML = "";
  if (face === null) { el.classList.add("misfire"); el.textContent = "?"; return; }
  el.classList.remove("misfire");
  for (let i = 0; i < 9; i++) { const p = document.createElement("span"); p.className = "pip" + (face && PIPS[face].includes(i) ? " on" : ""); el.appendChild(p); }
}
function setDice(f) { drawDie($("#h0"), f.house[0]); drawDie($("#h1"), f.house[1]); drawDie($("#p0"), f.player[0]); drawDie($("#p1"), f.player[1]); }
function tumble(on) { for (const id of ["h0", "h1", "p0", "p1"]) $("#" + id).classList.toggle("rolling", on); }

/* ---------- state ---------- */
async function refresh() {
  try { STATE = await api("/api/game/state"); } catch (e) { return; }
  const s = STATE;
  if (me && !s.players.find(p => p.id === me.id)) { me = null; localStorage.removeItem("qt_game_me"); }
  $("#me-label").textContent = me ? me.nick : "you";
  $("#chip-title").textContent = `Chip: ${s.backend} · ${s.label}`;
  $("#seatsmini").innerHTML = s.players.map(p => `<span style="color:${p.colour}">■</span> ${p.nick}: ${p.qredits} Qredits${p.point ? " · point " + p.point : ""}`).join(" · ") || "no one seated yet";
  $("#joinurl").textContent = s.join_url;
  if (!$("#qr").src) $("#qr").src = "/qr.png";
  $("#ticker").innerHTML = s.host_lines.map(l => `<li>${l.line} <span class="muted">(${l.source})</span></li>`).join("");
  if (!rolling && document.activeElement !== $("#level")) { $("#level").value = Math.round(s.level * 100); $("#levelval").textContent = Math.round(s.level * 100) + " %"; $("#levelbar").style.width = Math.round(s.level * 100) + "%"; }
  $("#shots100").checked = s.shots >= 100;
  drawChip(s);
  if (s.last && !rolling && lastShown !== s.last.bits + s.last.aggregate.rolls && (!me || s.last.player === me.id)) showResult(s.last);
  if (window.Table3D) window.Table3D.setEntangled(!!me && !(s.last && lastShown));
  $("#thread").classList.toggle("on", !!me && !(s.last && lastShown));
}

function showResult(r) {
  lastShown = r.bits + r.aggregate.rolls;
  setDice(r.faces);
  const b = $("#badge"); b.textContent = r.badge; b.className = "badge " + (r.ok ? "ok" : "bad");
  let t = `${r.nick}: house ${r.faces.house.map(f => f ?? "?").join("+")} · you ${r.faces.player.map(f => f ?? "?").join("+")}`;
  if (r.player_total) t += ` = ${r.player_total}`;
  t += ` → <b>${r.outcome}</b>`;
  if (r.qredits !== undefined) t += ` · ${r.qredits} Qredits`;
  t += `<div class="small muted">${r.entangled ? "entangled circuit" : "independent circuit"} (coin ${r.coin} vs level ${r.level}) · ${r.shots} shot${r.shots > 1 ? "s" : ""} · entanglement entropy ${r.entropy_bits}/${r.entropy_max} bits · ${r.engine}</div>`;
  $("#result").innerHTML = t;
  $("#fid").textContent = `fidelity ${r.fidelity.fidelity} (${r.fidelity.two_qubit_gates} two-qubit gates, depth ${r.fidelity.depth}, from calibration)`;
  $("#thread").classList.remove("on");
  if (window.Table3D) window.Table3D.setEntangled(false);
}

/* ---------- chip map zoomed to the used region ---------- */
async function loadChip() { CHIP = await api("/api/chipmap"); drawChip(STATE); }
function drawChip(s) {
  const el = $("#chip"); if (!CHIP || !s) return;
  const reg = s.region;
  const PAD = 0.8;
  el.setAttribute("viewBox", `${reg.x0 - PAD} ${reg.y0 - PAD} ${reg.w + 2 * PAD} ${Math.max(reg.h, 2) + 2 * PAD}`);
  const owner = {}, heart = {}, mine = new Set();
  for (const p of s.players) { for (const d of p.player) for (const q of d) owner[q] = p.colour; for (const d of p.house) for (const q of d) heart[q] = p.colour; if (me && p.id === me.id) for (const d of p.player.concat(p.house)) for (const q of d) mine.add(q); }
  let svg = "";
  for (const e of CHIP.pairs) { const a = CHIP.pos[e.u], b = CHIP.pos[e.v]; svg += `<line class="e" x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}"/>`; }
  for (const p of s.players) for (const [h, q] of p.links) { const a = CHIP.pos[h], b = CHIP.pos[q]; const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2 - 0.9; svg += `<path class="link" d="M${a[0]} ${a[1]} Q ${mx} ${my} ${b[0]} ${b[1]}" stroke="${p.colour}"/>`; }
  for (const [q, [x, y]] of Object.entries(CHIP.pos)) {
    if (heart[q]) svg += `<path class="heart ${mine.has(+q) ? "mine" : ""}" transform="translate(${x - 0.42},${y - 0.42}) scale(0.035)" d="M12 21s-7-4.5-9.5-9C.5 8 3 4 7 4c2 0 3.5 1 5 3 1.5-2 3-3 5-3 4 0 6.5 4 4.5 8-2.5 4.5-9.5 9-9.5 9z"/>`;
    else svg += `<circle class="q ${mine.has(+q) ? "mine" : ""}" cx="${x}" cy="${y}" r="${owner[q] ? 0.36 : 0.22}" ${owner[q] ? `fill="${owner[q]}"` : ""}/>`;
    svg += `<text x="${x}" y="${y + 0.75}">${q}</text>`;
  }
  el.innerHTML = svg;
}

/* ---------- actions ---------- */
async function join() {
  const nick = prompt("Pick a nickname (no account, nothing personal stored):", me ? me.nick : "");
  if (nick === null) return;
  try { me = await api("/api/game/join", { nick }); } catch (e) { alert(e.message); return; }
  localStorage.setItem("qt_game_me", JSON.stringify(me));
  $("#result").innerHTML = `${me.nick} seated with ${me.qredits} Qredits. Your dice: qubits ${me.player.map(d => d.join(",")).join(" and ")}; the house's hearts: ${me.house.map(d => d.join(",")).join(" and ")}.`;
  lastShown = null;
  if (window.Table3D) window.Table3D.setEntangled(true);
  refresh();
}
async function roll() {
  if (rolling) return;
  if (!me) { await join(); if (!me) return; }
  rolling = true; $("#roll").disabled = true;
  const b = $("#badge"); b.textContent = "circuit running on the chip model, verifier checking…"; b.className = "badge idle";
  tumble(true); if (window.Table3D) window.Table3D.startTumble();
  try {
    const r = await api("/api/game/roll", { player: me.id, level: $("#level").value / 100, shots: $("#shots100").checked ? 100 : 1 });
    if (window.Table3D) await window.Table3D.landOn(r.faces.house.map(f => f || 1), r.faces.player.map(f => f || 1)); else await new Promise(x => setTimeout(x, 700));
    tumble(false); showResult(r); STATE.last = r;
  } catch (e) { tumble(false); $("#result").textContent = "roll failed: " + e.message; }
  rolling = false; $("#roll").disabled = false;
}

$("#roll").onclick = roll;
$("#join").onclick = join;
$("#level").oninput = () => { $("#levelval").textContent = $("#level").value + " %"; $("#levelbar").style.width = $("#level").value + "%"; };
$("#qrbtn").onclick = () => $("#qrmodal").classList.remove("hidden");
$("#qrclose").onclick = () => $("#qrmodal").classList.add("hidden");
if (location.pathname === "/join" && !me) setTimeout(join, 300);
for (const id of ["h0", "h1", "p0", "p1"]) drawDie($("#" + id), 0);

/* 3D table by default; ?view=2d or no WebGL keeps the 2D table */
const want3d = params.get("view") === "3d" || (DEFAULT_3D && params.get("view") !== "2d");
const gl = (() => { try { const c = document.createElement("canvas"); return !!(c.getContext("webgl2") || c.getContext("webgl")); } catch (e) { return false; } })();
window.TABLE3D_SIMPLE = true;
if (want3d && gl) { const sc = document.createElement("script"); sc.type = "module"; sc.src = "/static/table3d.js"; document.body.appendChild(sc); }

refresh(); loadChip(); setInterval(refresh, 3000);
const es = new EventSource("/api/stream"); es.onmessage = (m) => { const ev = JSON.parse(m.data); if (["host_line", "player_joined"].includes(ev.type)) refresh(); };

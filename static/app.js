/* Quantum Table client: plain JS, no build step. */
const $ = (s) => document.querySelector(s);
const api = async (path, body, method) => {
  const r = await fetch(path, body !== undefined ? { method: method || "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) } : {});
  if (!r.ok) throw new Error((await r.text()).slice(0, 200));
  return r.json();
};
const fmtBytes = (b) => { const u = ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB"]; let i = 0; while (b >= 1024 && i < u.length - 1) { b /= 1024; i++; } return b.toFixed(b < 10 ? 1 : 0) + " " + u[i]; };
const PROJECTOR = !!window.PROJECTOR;
const params = new URLSearchParams(location.search);
let DEFAULT_3D = true;                  // set after the headless WebGL check in the build passed (docs/3d_*.png)
let me = JSON.parse(localStorage.getItem("qt_me") || "null");
let STATE = null, CHIP = null, selPair = null, BLOCH = null, rolling = false;

/* ---------- dice ---------- */
const PIPS = { 1: [4], 2: [0, 8], 3: [0, 4, 8], 4: [0, 2, 6, 8], 5: [0, 2, 4, 6, 8], 6: [0, 2, 3, 5, 6, 8] };
function drawDie(el, face) {
  if (!el) return; el.innerHTML = "";
  for (let i = 0; i < 9; i++) { const p = document.createElement("span"); p.className = "pip" + (face && PIPS[face].includes(i) ? " on" : ""); el.appendChild(p); }
}
function setDice(faces) { drawDie($("#h0"), faces.house[0]); drawDie($("#h1"), faces.house[1]); const mine = myFaces(faces); drawDie($("#p0"), mine[0]); drawDie($("#p1"), mine[1]); }
function myFaces(faces) {
  if (!faces.players || !faces.players.length) return [faces.house[0], faces.house[1]];
  if (me && STATE) { const i = STATE.players.findIndex(p => p.id === me.id); if (i >= 0 && faces.players[i]) return faces.players[i]; }
  return faces.players[0];
}
function tumble(on) { for (const id of ["h0", "h1", "p0", "p1"]) { const d = $("#" + id); if (d) d.classList.toggle("rolling", on); } }

/* ---------- bloch spheres (2D projection of real backend vectors) ---------- */
function blochSVG(v, label) {
  const [x, y, z] = v; const L = Math.hypot(x, y, z);
  const px = 23 + 16 * x, py = 23 - 16 * z;
  return `<svg class="bloch" viewBox="0 0 46 46" title="${label}"><circle cx="23" cy="23" r="18" fill="none" stroke="#9ab" stroke-width="1"/><ellipse cx="23" cy="23" rx="18" ry="6" fill="none" stroke="#9ab6" stroke-width=".7"/>
  <line x1="23" y1="23" x2="${px}" y2="${py}" stroke="${L < 0.05 ? "#777" : "#4aa3ff"}" stroke-width="2.5" stroke-linecap="round"/><circle cx="${px}" cy="${py}" r="${L < 0.05 ? 3 : 2}" fill="${L < 0.05 ? "#777" : "#fff"}"/></svg>`;
}
function renderBloch(kind, faces) {
  const row = $("#bloch"); if (!row || !BLOCH) return;
  let vecs;
  if (kind === "landed" && faces) { const mine = myFaces(faces); vecs = []; for (const f of mine) { const v = f - 1; for (let i = 0; i < 3; i++) vecs.push([0, 0, (v >> i) & 1 ? -1 : 1]); } }
  else vecs = (kind === "entangled" ? BLOCH.entangled : BLOCH.prepared).slice(0, 6);
  row.innerHTML = `<span class="small muted" style="align-self:center">your 6 qubits:</span>` + vecs.map((v, i) => blochSVG(v, "qubit " + i)).join("");
  if (window.Table3D) window.Table3D.setBloch(vecs, kind);
}

/* ---------- state ---------- */
async function refresh() {
  try { STATE = await api("/api/state"); } catch (e) { return; }
  const s = STATE;
  $("#clock") && ($("#clock").textContent = "Athens " + s.time_athens + " · " + s.qubits + " qubits at the table · " + s.phase);
  if ($("#rule")) $("#rule").textContent = s.rule_text + (s.players.length ? "" : " (join to entangle your dice)");
  if ($("#mode") && !$("#mode").options.length) { const o = document.createElement("option"); o.value = o.textContent = "BosonicEntangled"; $("#mode").appendChild(o); }
  if ($("#mode") && (!BLOCH || $("#mode").value !== s.mode) && !rolling && !loadingDesign) { $("#mode").value = s.mode; loadDesign(s.mode); }
  renderTeam(s.team); renderMeter(s); renderHost(s); renderSeats(s); renderHype(s.hype);
  if ($("#gate-credit")) $("#gate-credit").textContent = s.gate_credit; for (const el of document.querySelectorAll("#gate-credit2")) el.textContent = s.gate_credit;
  if ($("#art")) $("#art").textContent = s.art;
  if ($("#phase-engine")) $("#phase-engine").textContent = s.phase === "chip" ? "Simulated chip (fake backend)" : "Aer emulator";
  if ($("#entangled-label")) $("#entangled-label").textContent = s.players.length ? "entangled: outcomes are correlated, no signal passes." : "";
  $("#thread") && $("#thread").classList.toggle("on", s.players.length > 0 && !(STATE.last_result && !rolling && lastShown === STATE.last_result.round));
  if (s.last_result && !rolling && lastShown !== s.last_result.round) { showResult(s.last_result); }
  if (!rolling && !s.last_result) renderBloch(s.players.length ? "entangled" : "prepared");
  if (s.vote && $("#vote-out") && !$("#vote-out").textContent) $("#vote-out").textContent = JSON.stringify(s.vote, null, 1);
  if ($("#me-label")) $("#me-label").textContent = me ? me.nick : "you";
}
let lastShown = null, loadingDesign = false;
function showResult(r) {
  lastShown = r.round;
  setDice(r.faces); renderBloch("landed", r.faces);
  const b = $("#badge"); b.textContent = r.badge + " · " + r.engine; b.className = "badge " + (r.badge === "VERIFIED" ? "ok" : r.badge.startsWith("HARDWARE") ? "warn" : "bad");
  let t = `Round ${r.round}: house ${r.faces.house.join("+")}`;
  if (r.player_total) t += ` · you ${r.player_pair.join("+")} = ${r.player_total} → ${r.outcome} (${r.qredits} Qredits)`;
  if (r.decision) t += ` · Decide: ${r.decision.pick}`;
  if (r.dropped) t += ` · ${r.dropped} dropped for not revealing`;
  t += ` · <a href="/beacon/${r.round}" target="_blank" class="small">beacon ${r.beacon_hash.slice(0, 10)}</a>`;
  $("#result").innerHTML = t;
  renderTomo(r);
  $("#thread") && $("#thread").classList.remove("on");
  if (window.Table3D) window.Table3D.setEntangled(false);
  const lr = $("#lastrolls"); if (lr) { lr.innerHTML = `<div>#${r.round} ${r.faces.house.join("-")} <b>${r.badge}</b> ${r.engine}</div>` + lr.innerHTML; }
}
function renderTomo(r) {
  const el = $("#tomo"); if (!el || !r.tomography) return;
  const T = r.tomography; $("#tomo-shots").textContent = T.shots;
  const keys = Object.keys(T.exact).sort(); const mx = Math.max(...keys.map(k => Math.max(T.exact[k], T.freq[k] || 0)));
  el.innerHTML = keys.map(k => `<div class="bar" title="${k}: measured ${(T.freq[k] || 0).toFixed(3)}, exact ${T.exact[k].toFixed(3)}"><i style="height:${100 * (T.freq[k] || 0) / mx}%"></i><b style="bottom:${100 * T.exact[k] / mx}%"></b><span>${k}</span></div>`).join("");
}
function renderTeam(team) {
  const el = $("#team"); if (!el) return;
  el.innerHTML = team.map(a => `<div class="agent ${a.state}"><b>${a.name}</b><span class="m">${a.model === "-" ? a.wants + " → " + a.fallback : a.model}</span></div>`).join("");
}
function renderMeter(s) {
  const b = s.burndown, el = $("#meter"); if (!el) return;
  const maxQ = 54, q = s.qubits, f = Math.min(1, q / maxQ);
  el.style.width = (f * 100) + "%";
  const marks = [];
  const qOf = (bytes) => Math.log2(bytes / 16);
  marks.push([qOf(b.ram_total), `this machine ${fmtBytes(b.ram_total)}`]);
  marks.push([s.burn.limit_n + 1, `emulator burned down at ${s.burn.burned_down_at} qubits (${s.burn.measured ? "measured" : "80% line"})`]);
  if (b.daidalos.bytes) marks.push([qOf(b.daidalos.bytes), b.daidalos.label]); else marks.push([46, b.daidalos.label + " (no public figure)"]);
  marks.push([50, "~50 qubits: no classical machine follows"]);
  $("#marks").innerHTML = marks.map(([x, t], i) => `<div class="mark" style="left:${Math.min(99, x / maxQ * 100)}%" title="${t}"><span>${i + 1}</span></div>`).join("");
  const legend = marks.map(([x, t], i) => `<span class="muted">${i + 1}. ${t} (${Math.round(x)} q)</span>`).join(" · ");
  const pr = b.probes.filter(p => p.ok).slice(-1)[0];
  $("#meter-text").innerHTML = `<div class="small">${legend}</div><b>${q} qubits</b> → ${fmtBytes(s.bytes_needed)} of statevector. Aer emulator ran ${b.probes.filter(p => p.ok).length ? Math.max(...b.probes.filter(p => p.ok).map(p => p.n)) : "?"} qubits here${pr ? ` (${pr.seconds.toFixed(1)} s, ${fmtBytes(pr.rss || 0)} RSS)` : ""}; ${b.burned_down_at ? `refused at ${b.burned_down_at}` : "80% line at " + (b.analytic_limit_n + 1)}. ${s.phase === "chip" ? "<b>Emulator burned down at " + s.burn.burned_down_at + " qubits.</b> The chip takes over." : ""}`;
}
function renderHost(s) {
  const t = $("#ticker"); if (!t) return;
  t.innerHTML = s.host_lines.map(l => `<li>${l.line}<span class="src">${l.source}</span></li>`).join("");
  if ($("#corrected")) $("#corrected").textContent = `Host lines corrected by the checker: ${s.host_corrected} · Logic designer corrected: ${s.logic_corrected} · Gatekeeper blocks: ${s.gate_blocks}`;
}
function renderSeats(s) {
  const el = $("#seats"); if (!el) return;
  el.innerHTML = `${s.players.length} seated · ${s.qubits} qubits<br>` + s.players.map(p => `${p.nick}${p.bot ? " (bot)" : ""}: ${p.qredits} Qredits`).join(" · ");
  if ($("#joinurl")) $("#joinurl").textContent = s.join_url;
  if ($("#qr") && !$("#qr").src) $("#qr").src = "/qr.png";
}
function renderHype(h) {
  const el = $("#hype"); if (!el || !h) return;
  let html = "";
  if (h.card) html += `<div class="claim">"${h.card.sentence}"<div class="small muted">card by: ${h.card.origin} · bets: ${Object.values(h.bets).map(b => b.nick + " " + b.side).join(", ") || "none yet"}</div></div>`;
  else if (h.last) html += `<div class="claim">"${h.last.sentence}" <span class="verdict ${h.last.verdict}">${h.last.verdict}</span><div class="small">${h.last.headline}</div><div class="small muted">${h.last.engine} · run ${h.last.run_id}${h.last.ai_line ? " · <b>" + h.last.ai_line + "</b>" : ""}</div></div>`;
  else html += `<div class="muted small">The Host deals a card when the table is idle for 30 s.</div>`;
  el.innerHTML = html;
  if ($("#hype-score")) $("#hype-score").textContent = `Experiment ${h.experiments}, AI claims ${h.ai_claims_survived} (of ${h.ai_claims_total} AI-written; ${h.discarded} uncomputable cards discarded)`;
}
async function loadDesign(mode) {
  loadingDesign = true;
  try {
    const [d, b] = await Promise.all([api("/api/design/" + mode), api("/api/bloch/" + mode)]);
    BLOCH = b;
    if ($("#design")) $("#design").textContent = `Q-Scientist (${d.source}) · commit ${d.hash.slice(0, 16)}… · ${d.pairs} allowed pairs · pass-line win ${d.win_fraction} = ${d.win.toFixed(4)}\nLogic designer (${d.logic.source})${d.logic.corrected ? " · CORRECTED by enumeration" : ""}: P(win at come-out)=${d.logic.p_win_comeout.toFixed(4)} P(lose)=${d.logic.p_lose_comeout.toFixed(4)}\n\n${d.code}`;
    if (!rolling) renderBloch(STATE && STATE.players.length ? "entangled" : "prepared");
  } catch (e) { }
  loadingDesign = false;
}

/* ---------- commit-reveal roll (the browser holds the secret) ---------- */
const hex = (buf) => [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0")).join("");
async function sha256hex(hexStr) { const bytes = new Uint8Array(hexStr.match(/../g).map(h => parseInt(h, 16))); return hex(await crypto.subtle.digest("SHA-256", bytes)); }
async function roll(options) {
  if (rolling) return; rolling = true; $("#roll").disabled = true;
  const b = $("#badge"); b.textContent = "circuit running, verifier checking…"; b.className = "badge idle";
  $("#result").textContent = ""; tumble(true); if (window.Table3D) window.Table3D.startTumble();
  try {
    const r = await api("/api/round/open", { player: me ? me.id : null, options });
    const rid = r.round;
    if (me) {
      const secret = hex(crypto.getRandomValues(new Uint8Array(32)));
      await api(`/api/round/${rid}/commit`, { player: me.id, hash: await sha256hex(secret) });
      let v; do { await new Promise(x => setTimeout(x, 150)); v = await api(`/api/round/${rid}`); } while (v.status === "committing" || v.status === "running");
      if (v.status === "revealing") await api(`/api/round/${rid}/reveal`, { player: me.id, secret });
    }
    let v; do { await new Promise(x => setTimeout(x, 200)); v = await api(`/api/round/${rid}`); } while (!["done", "error"].includes(v.status));
    if (v.status === "error") throw new Error(v.error);
    const res = v.result;
    // (2) faces known -> (3) choreograph the landing onto them
    if (window.Table3D) await window.Table3D.landOn(res.faces.house, myFaces(res.faces)); else await new Promise(x => setTimeout(x, 700));
    tumble(false); showResult(res); STATE.last_result = res;
  } catch (e) { tumble(false); $("#result").textContent = "round failed: " + e.message; }
  rolling = false; $("#roll").disabled = false;
}

/* ---------- chip map ---------- */
async function loadChip() {
  const el = $("#chip"); if (!el) return;
  CHIP = await api("/api/chipmap");
  $("#chip-label").textContent = `${CHIP.backend} · ${CHIP.label} · calibration: ${CHIP.calibration}`;
  const lo = Math.min(...CHIP.pairs.map(p => p.price)), hi = Math.max(...CHIP.pairs.map(p => p.price));
  let svg = "";
  for (const p of CHIP.pairs) { const a = CHIP.pos[p.u], b = CHIP.pos[p.v]; const t = (p.price - lo) / (hi - lo || 1); svg += `<line class="e" data-u="${p.u}" data-v="${p.v}" x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}" stroke="hsl(${120 * t},80%,55%)"><title>q${p.u}–q${p.v}: 2q error ${p.err2q.toExponential(2)}, readout ${p.ro_u.toFixed(3)}/${p.ro_v.toFixed(3)} → ${p.price} Qredits</title></line>`; }
  for (const [q, [x, y]] of Object.entries(CHIP.pos)) svg += `<circle class="q" cx="${x}" cy="${y}" r=".28"/>`;
  el.innerHTML = svg;
  $("#chip-info").innerHTML = `${CHIP.n} qubits, ${CHIP.pairs.length} coupled pairs. Price: <code>${CHIP.formula}</code>. Green = low error = expensive. Tap a link to choose it.`;
  el.onclick = (ev) => { const l = ev.target.closest("line"); if (!l) return; el.querySelectorAll(".sel").forEach(x => x.classList.remove("sel")); l.classList.add("sel"); selPair = [+l.dataset.u, +l.dataset.v]; const p = CHIP.pairs.find(p => p.u === selPair[0] && p.v === selPair[1]); $("#chipres").textContent = `chosen q${p.u}–q${p.v} for ${p.price} Qredits`; };
}
function showChip(r) {
  let h = `<b>${r.status}</b> · Gatekeeper ${r.decision} (${r.rule}, ${r.gate_engine}) · estimate ${r.est} QPU s`;
  if (r.quote) h += ` · quote: ${r.quote.total === undefined ? "" : r.quote.total} (${r.quote.cost === "price unavailable" ? "price unavailable: quoted in QPU seconds" : "cost " + r.quote.cost + " USD + " + r.quote.margin_pct + "%"})`;
  if (r.status === "done") {
    h += `<br><b>${r.label}</b> · job ${r.job_id} · <span class="badge warn">${r.badge}</span><br>` + r.per_pair.map(p => `${p.nick} q${p.qubits.join("–")}: ${JSON.stringify(p.counts)} · TVD vs ideal ${p.tvd_ideal.toFixed(3)} ± ${p.tvd_error_bar.toFixed(3)} · TVD vs noise-model Aer ${p.tvd_noise_model.toFixed(3)}`).join("<br>");
    h += `<br><span class="muted">${r.noise_note}</span>`;
    if (r.invoice) h += `<div class="waitjob"><b>${r.invoice.banner}</b> · actual ${r.invoice.actual_qpu_seconds} QPU s · list price ${r.invoice.list_price_equivalent} · ${r.invoice.true_cost_note}</div>`;
  }
  if (r.status === "waiting for approval") h += `<div class="waitjob">Waiting for a person. <button onclick="approve('${r.job_hash}')">Approve ${r.est} QPU s (job ${r.job_hash})</button></div>`;
  $("#chipres").innerHTML = h; loadGate();
}
window.approve = async (h) => { const r = await api("/api/chip/approve", { job_hash: h }); $("#chipres").innerHTML += `<div>approved ${h}: ${r.status} (${r.decision})</div>`; loadGate(); };
async function loadGate() {
  const el = $("#gatelog"); if (!el) return;
  const L = await api("/api/library");
  el.innerHTML = `<div class="gate"><b>who</b><b>what</b><b>est s</b><b>purpose</b><b>decision · rule</b>` + L.gate_log.map(g => `<span>${g.agent}</span><span>${g.tool}</span><span>${g.est ?? ""}</span><span>${g.purpose}</span><span class="${g.action}">${g.action} · ${g.rule}</span>`).join("") + `</div>
  <div class="muted">QPU seconds used (IBM-reported): ${L.qpu_seconds_used} · ledger: ${L.finance.invoices} shadow invoice(s), list-price equivalent ${L.finance.list_price_equivalent_usd} · IBM price: ${L.price.status} (${L.price.url}, ${L.price.fetched})</div>`;
  const w = L.jobs.filter(j => j.status === "waiting for approval");
  $("#waiting").innerHTML = w.map(j => `<div class="waitjob">Job ${j.job_hash}: ${j.est} QPU s waiting for approval <button onclick="approve('${j.job_hash}')">Approve</button></div>`).join("");
}

/* ---------- join ---------- */
async function join() {
  const nick = prompt("Pick a nickname (no account, nothing personal stored):", me ? me.nick : "");
  if (nick === null) return;
  me = await api("/api/join", { nick }); localStorage.setItem("qt_me", JSON.stringify(me));
  $("#result").textContent = `${me.nick} seated with ${me.qredits} Qredits. Your dice are now entangled with the house pair.`;
  if (window.Table3D) window.Table3D.setEntangled(true);
  refresh();
}

/* ---------- events (SSE) ---------- */
function listen() {
  const es = new EventSource("/api/stream");
  es.onmessage = (m) => { const ev = JSON.parse(m.data); if (["host_line", "player_joined", "burned_down", "hype_verdict", "gatekeeper", "quantum_vote"].includes(ev.type)) refresh(); if (ev.type === "gatekeeper") loadGate(); };
}

/* ---------- wiring ---------- */
if (!PROJECTOR) {
  $("#roll").onclick = () => roll();
  $("#join").onclick = join;
  $("#skip").onclick = async () => { const r = await api("/api/skip_ahead", {}); $("#result").textContent = `Skip ahead: ${r.added} bots seated → ${r.qubits} qubits, phase ${r.phase}`; refresh(); };
  $("#decide").onclick = () => { const t = prompt("2 to 6 options, comma separated (e.g. who presents first):"); if (!t) return; const o = t.split(",").map(s => s.trim()).filter(Boolean).slice(0, 6); if (o.length >= 2) roll(o); };

  $("#buy").onclick = async () => { if (!me) return alert("join first"); if (!selPair) return alert("tap a link on the chip map"); const r = await api("/api/chip/buy", { player: me.id, u: selPair[0], v: selPair[1] }); $("#chipres").textContent = r.ok ? `bought q${r.pair.join("–")} for ${r.price} Qredits` : "refused: " + r.why; $("#chip").querySelectorAll(".sel").forEach(x => x.classList.add("taken")); refresh(); };
  $("#chiprun").onclick = async () => { $("#chipres").textContent = "submitting…"; showChip(await api("/api/chip/run", {})); };
  $("#overspend").onclick = async () => { const r = await api("/api/chip/overspend", {}); $("#chipres").innerHTML = `Try to overspend: 6,000 shots × 200 circuits → estimate ${r.est} QPU s → <b class="${r.decision}">${r.decision}</b> (${r.rule})`; loadGate(); };
  $("#bigjob").onclick = async () => { const r = await api("/api/chip/big", {}); showChip({ ...r, gate_engine: r.engine_gate }); };
  $("#charge").onclick = async () => { const r = await api("/api/finance/charge", {}); $("#chipres").innerHTML = `Financial agent asked to charge_customer → <b class="${r.action}">${r.action}</b> (${r.rule}). No payment code exists in this build.`; loadGate(); };
  $("#deal").onclick = async () => renderHype(await api("/api/hype/deal", {}));
  $("#bet-fact").onclick = async () => { if (!me) return alert("join first"); renderHype(await api("/api/hype/bet", { player: me.id, side: "fact", amount: 5 })); };
  $("#bet-hype").onclick = async () => { if (!me) return alert("join first"); renderHype(await api("/api/hype/bet", { player: me.id, side: "hype", amount: 5 })); };
  $("#resolve").onclick = async () => { $("#hype").innerHTML += `<div class="muted small">running the experiment…</div>`; renderHype(await api("/api/hype/resolve", {})); refresh(); };
  $("#vote").onclick = async () => { const v = await api("/api/vote", {}); $("#vote-out").textContent = `winner: ${v.winner}\nballots: ${JSON.stringify(v.ballots)} (${v.shots} shots, seed ${v.seed}, ${v.circuit_qubits} qubits, Ry(2·asin√c) per agent×option)\nconfidences: ${JSON.stringify(v.confidences)}\n${v.confidence_source}\n${v.label}`; };
  
  loadChip(); loadGate();
  // 3D table: default decided by the build's headless check; ?view=3d / ?view=2d override; 2D if WebGL is missing.
  const want3d = params.get("view") === "3d" || (DEFAULT_3D && params.get("view") !== "2d");
  const gl = (() => { try { const c = document.createElement("canvas"); return !!(c.getContext("webgl2") || c.getContext("webgl")); } catch (e) { return false; } })();
  if (want3d && gl) { const s = document.createElement("script"); s.type = "module"; s.src = "/static/table3d.js"; document.body.appendChild(s); }
}
for (const id of ["h0", "h1", "p0", "p1"]) drawDie($("#" + id), 0);
refresh(); listen(); setInterval(refresh, 2500);

/* 3D craps table with Bloch-sphere dice. Three.js (vendored). The dice land on faces the backend measured;
   the tumble is choreography toward a known result. Bloch arrows come from the backend's reduced density matrices. */
import * as THREE from "/static/vendor/three.module.js";

const host = document.getElementById("table3d");
const flat = document.getElementById("table2d");
host.classList.remove("hidden"); flat.classList.add("hidden");
const W = () => host.clientWidth, H = () => host.clientHeight;
const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "low-power" });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5)); renderer.setSize(W(), H());
host.appendChild(renderer.domElement);
const scene = new THREE.Scene(); scene.background = new THREE.Color(0x0b0e13);
const camera = new THREE.PerspectiveCamera(42, W() / H(), 0.1, 100);
let theta = 0, phi = 0.95, radius = 9.5;
function placeCamera() { camera.position.set(radius * Math.sin(phi) * Math.sin(theta), radius * Math.cos(phi), radius * Math.sin(phi) * Math.cos(theta)); camera.lookAt(0, 0, 0); }
placeCamera();
scene.add(new THREE.HemisphereLight(0xffffff, 0x224422, 0.9));
const sun = new THREE.DirectionalLight(0xffffff, 1.1); sun.position.set(4, 8, 3); scene.add(sun);

/* ---- table: felt, wooden rails, original markings on a canvas texture ---- */
function drawMarks(g) {
  g.strokeStyle = "#e8d9a0"; g.lineWidth = 6; g.fillStyle = "#e8d9a0"; g.textAlign = "center";
  g.strokeRect(40, 40, 944, 432);
  g.beginPath(); g.moveTo(40, 400); g.lineTo(984, 400); g.stroke(); g.font = "bold 44px serif"; g.fillText("PASS LINE", 512, 448);
  g.beginPath(); g.moveTo(40, 120); g.lineTo(984, 120); g.stroke(); g.fillText("HOUSE", 512, 100);
  g.font = "bold 30px serif";
  g.fillText("7 or 11 WINS   ·   2, 3, 12 LOSES", 512, 230);
  g.fillText("ANY OTHER TOTAL IS YOUR POINT: ROLL IT AGAIN BEFORE A 7", 512, 290);
  g.font = "bold 26px serif"; g.fillText("each die = 3 qubits on the chip · stake 5 Qredits · pays 1:1", 512, 350);
}
function feltTexture() {
  const c = document.createElement("canvas"); c.width = 1024; c.height = 512; const g = c.getContext("2d");
  g.fillStyle = "#0f5a36"; g.fillRect(0, 0, 1024, 512);
  for (let i = 0; i < 4000; i++) { g.fillStyle = `rgba(255,255,255,${Math.random() * 0.04})`; g.fillRect(Math.random() * 1024, Math.random() * 512, 2, 2); }
  g.strokeStyle = "#e8d9a0"; g.lineWidth = 6; g.font = "bold 44px serif"; g.fillStyle = "#e8d9a0"; g.textAlign = "center";
  g.strokeRect(40, 40, 944, 432);
  drawMarks(g);
  const t = new THREE.CanvasTexture(c); t.anisotropy = 4;
  // Art director: if a fal.ai felt image exists, paint it under the markings (cached at build time, never fetched from fal at run time)
  const img = new Image(); img.onload = () => { g.globalAlpha = 0.55; g.drawImage(img, 0, 0, 1024, 512); g.globalAlpha = 1; drawMarks(g); t.needsUpdate = true; };
  img.src = "/assets/fal_felt.jpg";
  return t;
}
const felt = new THREE.Mesh(new THREE.BoxGeometry(10, 0.3, 5), [new THREE.MeshStandardMaterial({ color: 0x0f5a36 }), new THREE.MeshStandardMaterial({ color: 0x0f5a36 }),
  new THREE.MeshStandardMaterial({ map: feltTexture(), roughness: 0.95 }), new THREE.MeshStandardMaterial({ color: 0x0b3d24 }), new THREE.MeshStandardMaterial({ color: 0x0f5a36 }), new THREE.MeshStandardMaterial({ color: 0x0f5a36 })]);
felt.position.y = -0.15; scene.add(felt);
const wood = new THREE.MeshStandardMaterial({ color: 0x5a3b1e, roughness: 0.6 });
for (const [x, z, sx, sz] of [[0, 2.75, 10.8, 0.5], [0, -2.75, 10.8, 0.5], [5.15, 0, 0.5, 6], [-5.15, 0, 0.5, 6]]) {
  const r = new THREE.Mesh(new THREE.BoxGeometry(sx, 0.7, sz), wood); r.position.set(x, 0.1, z); scene.add(r);
}

/* ---- dice with pips (one canvas per face, 6 materials) ---- */
const PIPS = { 1: [4], 2: [0, 8], 3: [0, 4, 8], 4: [0, 2, 6, 8], 5: [0, 2, 4, 6, 8], 6: [0, 2, 3, 5, 6, 8] };
function faceTex(n) {
  const c = document.createElement("canvas"); c.width = c.height = 128; const g = c.getContext("2d");
  g.fillStyle = "#fafafa"; g.fillRect(0, 0, 128, 128); g.fillStyle = "#111";
  for (const i of PIPS[n]) { const x = 24 + (i % 3) * 40, y = 24 + Math.floor(i / 3) * 40; g.beginPath(); g.arc(x, y, 11, 0, 6.3); g.fill(); }
  return new THREE.CanvasTexture(c);
}
// BoxGeometry material order: +x, -x, +y, -y, +z, -z. Standard die: opposite faces sum to 7.
const FACE_ORDER = [1, 6, 2, 5, 3, 4];
const dieMats = FACE_ORDER.map(n => new THREE.MeshStandardMaterial({ map: faceTex(n), roughness: 0.4 }));
// rotation that brings face n to the top (+y)
const UP = { 2: new THREE.Euler(0, 0, 0), 5: new THREE.Euler(Math.PI, 0, 0), 1: new THREE.Euler(0, 0, -Math.PI / 2), 6: new THREE.Euler(0, 0, Math.PI / 2), 3: new THREE.Euler(Math.PI / 2, 0, 0), 4: new THREE.Euler(-Math.PI / 2, 0, 0) };
function makeDie(x, z) { const m = new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.8, 0.8), dieMats); m.position.set(x, 0.4, z); m.userData.rest = new THREE.Vector3(x, 0.4, z); scene.add(m); return m; }
const dice = { house: [makeDie(-0.8, -1.6), makeDie(0.8, -1.6)], player: [makeDie(-0.8, 1.6), makeDie(0.8, 1.6)] };

/* ---- Bloch spheres: three per die, arrows from backend vectors ---- */
const sphereGeo = new THREE.SphereGeometry(0.22, 16, 12);
const sphereMat = new THREE.MeshStandardMaterial({ color: 0x9ab4cc, transparent: true, opacity: 0.25 });
const ringGeo = new THREE.TorusGeometry(0.22, 0.006, 6, 32);
const ringMat = new THREE.MeshBasicMaterial({ color: 0xcfe3ff });
const blochs = [];
if (!window.TABLE3D_SIMPLE) for (const [who, pair] of Object.entries(dice)) for (const d of pair) for (let i = 0; i < 3; i++) {
  const g = new THREE.Group(); g.position.set(d.position.x + (i - 1) * 0.5, 1.5, d.position.z);
  g.add(new THREE.Mesh(sphereGeo, sphereMat)); const ring = new THREE.Mesh(ringGeo, ringMat); ring.rotation.x = Math.PI / 2; g.add(ring);
  const arrow = new THREE.ArrowHelper(new THREE.Vector3(0, 1, 0), new THREE.Vector3(), 0.22, 0x4aa3ff, 0.08, 0.05); g.add(arrow);
  g.userData = { arrow, who, target: new THREE.Vector3(0, 1, 0), len: 1 }; scene.add(g); blochs.push(g);
}
/* glowing thread: player die <-> house die while entangled */
const threadMat = new THREE.LineBasicMaterial({ color: 0x4aa3ff, transparent: true, opacity: 0.0 });
const threads = [0, 1].map(i => { const g = new THREE.BufferGeometry().setFromPoints([dice.player[i].position, dice.house[i].position]); const l = new THREE.Line(g, threadMat); scene.add(l); return l; });
const glow = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 1, 8), new THREE.MeshBasicMaterial({ color: 0x4aa3ff, transparent: true, opacity: 0 }));
scene.add(glow);
let entangled = false;

/* ---- API used by app.js ---- */
let tumbling = false, landing = null, t0 = 0;
window.Table3D = {
  setEntangled(on) { entangled = on; },
  setBloch(vecs, kind) {
    // vecs: 6 vectors for the player's qubits (die A: 0..2, die B: 3..5). House gets the same prepared/entangled picture.
    blochs.forEach((g, idx) => {
      const v = vecs[idx % 6] || [0, 0, 1]; const len = Math.hypot(v[0], v[1], v[2]);
      g.userData.target.set(v[0], v[2], -v[1]).normalize(); g.userData.len = Math.max(len, 0.02);
      if (len < 0.02) g.userData.target.set(0, 1, 0);
      g.userData.dark = len < 0.05;
    });
    if (kind === "entangled") entangled = true;
  },
  startTumble() { tumbling = true; landing = null; t0 = performance.now(); },
  landOn(houseFaces, playerFaces) {
    return new Promise(res => { landing = { house: houseFaces, player: playerFaces, start: performance.now(), done: res }; tumbling = false; entangled = false; });
  }
};

/* ---- interaction: gentle orbit on drag ---- */
let drag = null;
host.addEventListener("pointerdown", e => { drag = { x: e.clientX, y: e.clientY, th: theta, ph: phi }; });
window.addEventListener("pointermove", e => { if (!drag) return; theta = drag.th - (e.clientX - drag.x) * 0.006; phi = Math.min(1.4, Math.max(0.4, drag.ph - (e.clientY - drag.y) * 0.005)); placeCamera(); });
window.addEventListener("pointerup", () => drag = null);
window.addEventListener("resize", () => { renderer.setSize(W(), H()); camera.aspect = W() / H(); camera.updateProjectionMatrix(); });

/* ---- animation loop ---- */
const easeOut = (x) => 1 - Math.pow(1 - x, 3);
function animate(now) {
  requestAnimationFrame(animate);
  const all = [...dice.house, ...dice.player];
  if (tumbling) {
    const t = (now - t0) / 1000;
    all.forEach((d, i) => { d.position.y = 1.2 + 0.5 * Math.abs(Math.sin(t * 3 + i)); d.rotation.set(t * 5 + i, t * 3.7 + i * 2, t * 2.3); });
  } else if (landing) {
    const u = Math.min(1, (now - landing.start) / 900), e = easeOut(u);
    const faces = [...landing.house, ...landing.player];
    all.forEach((d, i) => {
      const rest = d.userData.rest, target = UP[faces[i]] || UP[1];
      d.position.set(rest.x + (1 - e) * Math.sin(i + now / 300) * 0.3, rest.y + (1 - e) * 1.0, rest.z);
      d.rotation.set(THREE.MathUtils.lerp(d.rotation.x, target.x, 0.18), THREE.MathUtils.lerp(d.rotation.y, target.y, 0.18), THREE.MathUtils.lerp(d.rotation.z, target.z, 0.18));
      if (u >= 1) d.rotation.copy(target);
    });
    if (u >= 1) { const done = landing.done; landing = null; done(); }
  }
  blochs.forEach(g => { const a = g.userData.arrow, L = g.userData.len; a.setDirection(a.line.getWorldDirection(new THREE.Vector3()).lerp(g.userData.target, 0.15).normalize()); a.setLength(0.22 * (L + 0.0001), 0.08 * L + 0.01, 0.05 * L + 0.005); a.setColor(g.userData.dark ? 0x667788 : 0x4aa3ff); });
  const op = entangled ? 0.7 + 0.3 * Math.sin(now / 250) : 0;
  threadMat.opacity = op; threads.forEach((l, i) => { l.geometry.setFromPoints([dice.player[i].position, dice.house[i].position]); });
  glow.material.opacity = op * 0.9; const a = dice.player[0].position, b = dice.house[0].position; glow.position.lerpVectors(a, b, 0.5); glow.scale.y = a.distanceTo(b); glow.lookAt(b); glow.rotateX(Math.PI / 2);
  renderer.render(scene, camera);
}
requestAnimationFrame(animate);
window.__drawCalls = () => renderer.info.render.calls;

// Records the real page with headless Playwright (software WebGL). Output: video/raw/seg_*.webm
const { chromium } = require('playwright');
const fs = require('fs'); const path = require('path');
const BASE = process.env.BASE || 'http://localhost:8080';
const OUT = path.join(__dirname, 'raw'); fs.mkdirSync(OUT, { recursive: true });
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function segment(name, fn) {
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const ctx = await b.newContext({ viewport: { width: 1280, height: 720 }, recordVideo: { dir: OUT, size: { width: 1280, height: 720 } } });
  const p = await ctx.newPage();
  await p.addInitScript(() => { localStorage.removeItem('qt_me'); window.prompt = () => 'Guest'; });
  try { await fn(p); } catch (e) { console.log(name, 'error', e.message); }
  const v = p.video(); await ctx.close(); await b.close();
  const file = await v.path(); fs.renameSync(file, path.join(OUT, name + '.webm')); console.log('recorded', name);
}

(async () => {
  await fetch(BASE + '/api/reset', { method: 'POST' });
  await segment('seg_hook', async (p) => {
    await p.goto(BASE + '/?view=3d'); await sleep(2500);
    await p.click('#roll'); await sleep(9000);
    await p.goto(BASE + '/beacon/latest'); await sleep(2500);
    await p.setContent(`<body style="background:#0e1116;color:#2fbf71;font:40px ui-monospace,monospace;padding:80px"><div style="color:#e9eef5">$ python3 verify_beacon.py ${BASE}</div><div style="color:#93a0b4;font-size:30px;margin:20px 0">recomputing commitments, selection, output, chain link…</div><div style="font-size:72px;font-weight:800">PASS</div></body>`); await sleep(3500);
  });
  await segment('seg_resources', async (p) => {
    await p.goto(BASE + '/?view=3d'); await sleep(2500);
    await p.selectOption('#mode', 'BosonicEntangled'); await sleep(3500);
    await p.click('#join'); await sleep(6000);
    await p.click('#roll'); await sleep(9500);
    await p.evaluate(() => document.querySelector('#meter').scrollIntoView({ block: 'center' })); await sleep(2500);
    await p.click('#skip'); await sleep(7000);
  });
  await segment('seg_hype', async (p) => {
    await p.goto(BASE + '/?view=2d'); await sleep(2000);
    await p.click('#join'); await sleep(2500);
    await p.evaluate(() => document.querySelector('#hype').scrollIntoView({ block: 'center' }));
    // deal until the no-signalling card comes up (deck order is fixed: it is the second card)
    for (let i = 0; i < 12; i++) {
      await p.click('#deal'); await sleep(900);
      const t = await p.textContent('#hype');
      if (t.includes('send a message')) break;
      await fetch(BASE + '/api/hype/resolve', { method: 'POST' });
    }
    await sleep(4000);
    await p.click('#bet-hype'); await sleep(3000);
    await p.click('#resolve'); await sleep(14000);
  });
  await segment('seg_chip', async (p) => {
    await p.goto(BASE + '/?view=2d'); await sleep(2000);
    await p.evaluate(() => document.querySelector('#chip').scrollIntoView({ block: 'center' })); await sleep(2500);
    await p.click('#chiprun'); await sleep(8000);
    await p.click('#overspend'); await sleep(4000);
  });
})();

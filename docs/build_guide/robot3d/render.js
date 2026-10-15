// Render views of the 3D robot to out/*.png:  node render.js [view ...]
const { chromium } = require('playwright');
const http = require('http'); const fs = require('fs'); const path = require('path');
const ROOT = __dirname;
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.png': 'image/png', '.json': 'application/json' };
const server = http.createServer((req, res) => {
  const f = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]));
  if (!f.startsWith(ROOT) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': TYPES[path.extname(f)] || 'application/octet-stream' }); fs.createReadStream(f).pipe(res);
});
const JOBS = {
  hero_labels: 'view=hero&labels=1',
  hero: 'view=hero', front: 'view=front', rear_labels: 'view=rear&labels=1', left: 'view=left', top_labels: 'view=top&labels=1',
  under_labels: 'view=under&labels=1', close: 'view=close',
};
(async () => {
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  const port = server.address().port;
  fs.mkdirSync(path.join(ROOT, 'out'), { recursive: true });
  const b = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const want = process.argv.slice(2).length ? process.argv.slice(2) : Object.keys(JOBS);
  for (const name of want) {
    const p = await b.newPage({ viewport: { width: 2400, height: 1600 } });
    p.on('console', (m) => { if (m.type() === 'error') console.log('console:', m.text()); });
    p.on('pageerror', (e) => console.log('pageerror:', e.message));
    await p.goto(`http://127.0.0.1:${port}/view.html?${JOBS[name] || name}`);
    await p.waitForFunction('window.READY === true', null, { timeout: 180000 });
    await p.screenshot({ path: path.join(ROOT, 'out', `${name}.png`) });
    console.log('rendered', name); await p.close();
  }
  await b.close(); server.close();
})();

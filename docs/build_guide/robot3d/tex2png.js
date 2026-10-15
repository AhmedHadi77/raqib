// SVG textures -> PNG (4x) for three.js
const { chromium } = require('playwright');
const fs = require('fs'); const path = require('path');
(async () => {
  const dir = path.join(__dirname, 'tex'); const b = await chromium.launch();
  for (const f of fs.readdirSync(dir).filter((x) => x.endsWith('.svg'))) {
    const svg = fs.readFileSync(path.join(dir, f), 'utf8');
    const w = +svg.match(/width="([\d.]+)"/)[1], h = +svg.match(/height="([\d.]+)"/)[1];
    const p = await b.newPage({ viewport: { width: Math.ceil(w), height: Math.ceil(h) }, deviceScaleFactor: 4 });
    await p.setContent(`<html><body style="margin:0;background:transparent">${svg}</body></html>`);
    await p.locator('svg').screenshot({ path: path.join(dir, f.replace('.svg', '.png')), omitBackground: true });
    await p.close();
  }
  await b.close(); console.log('png textures done');
})();

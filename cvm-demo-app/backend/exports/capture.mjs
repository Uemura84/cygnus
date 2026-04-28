import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const CHARTS = [
  'braskem_revenue_cogs',
  'braskem_margin_bridge',
  'braskem_distress_gauge',
  'vale_revenue_cogs',
  'vale_margin_bridge',
  'vale_distress_gauge',
];

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 3 });

  page.on('console', msg => {
    if (msg.type() === 'error') console.log('CONSOLE ERROR:', msg.text());
  });
  page.on('pageerror', err => console.log('PAGE ERROR:', err.message));

  console.log('Navigating to http://localhost:5173/?export=charts ...');
  await page.goto('http://localhost:5173/?export=charts', { waitUntil: 'networkidle' });

  console.log('Waiting for charts to render...');
  await page.waitForFunction(() => document.title === 'CHARTS_READY', { timeout: 15000 });
  await page.waitForTimeout(500);

  for (const id of CHARTS) {
    const el = await page.$(`#${id}`);
    if (!el) {
      console.log(`  ✗ ${id} — element not found`);
      continue;
    }
    const outPath = path.join(__dirname, `${id}.png`);
    await el.screenshot({ path: outPath, type: 'png' });
    console.log(`  ✓ ${outPath}`);
  }

  await browser.close();
  console.log('\nDone.');
})();

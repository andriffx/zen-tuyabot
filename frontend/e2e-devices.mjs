import { chromium } from 'playwright';

const base = process.env.BASE_URL ?? 'http://localhost:5173';
const out = process.env.SHOT_DIR ?? null;
const USER = process.env.SMOKE_USER ?? 'root';
const PASS = process.env.SMOKE_PASS ?? 'password-panjang';

// Screenshots are opt-in: with SHOT_DIR unset nothing is written, so a normal
// run leaves the working tree clean (they are for manual reports, not the repo).
async function snap(name, fullPage = true) {
	if (!out) return;
	await page.screenshot({ path: `${out}/${name}.png`, fullPage });
}

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const errors = [];
page.on('pageerror', (error) => errors.push(error.message));

const results = [];
function check(name, ok, extra = '') {
	results.push({ name, ok: Boolean(ok) });
	console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${extra ? ` — ${extra}` : ''}`);
}

// Login.
await page.goto(base + '/login', { waitUntil: 'networkidle' });
if (new URL(page.url()).pathname !== '/login') {
	await page.goto(base + '/', { waitUntil: 'networkidle' });
} else {
	await page.fill('#username', USER);
	await page.fill('#password', PASS);
	await page.click('button[type=submit]');
	await page.waitForTimeout(2000);
}
if (new URL(page.url()).pathname === '/login') {
	await page.fill('#username', USER);
	await page.fill('#password', PASS);
	await page.click('button[type=submit]');
	await page.waitForTimeout(2000);
}

// Go to devices and create one through the dialog.
await page.goto(base + '/devices', { waitUntil: 'networkidle' });
await page.waitForTimeout(1000);

const existing = await page.locator('[data-slot="card"]').count();
if (existing === 0) {
	await page.click('text=Tambah device pertama');
} else {
	await page.click('text=Tambah device');
}
await page.waitForTimeout(600);

await page.fill('#dev-name', 'pompa-uji');
await page.fill('#dev-label', 'Pompa Uji');
await page.fill('#dev-tuya', 'bf00000000000001');
await page.fill('#dev-key', 'local-key-uji');
await page.fill('#dev-ip', '192.168.1.77');
await page.click('text=Simpan');
await page.waitForTimeout(2500);

const created = await page.isVisible('text=Pompa Uji');
check('device appears after creation', created);
await snap(`10-device-created`);

// The card must carry the template DPS and show as offline (no real device).
const body = await page.locator('body').innerText();
check('card shows the offline explanation', body.includes('Perangkat tidak merespons'));
check('card shows MATI/unknown switch state', /MATI|tidak diketahui/.test(body));

// Detail page loads with the DPS table.
await page.click('text=Detail');
await page.waitForTimeout(2000);
check('detail page opens', new URL(page.url()).pathname.startsWith('/devices/'), page.url());
const detail = await page.locator('body').innerText();
check('detail shows the DPS mapping table', detail.includes('Pemetaan DPS'));
check('detail maps switch to DP 1', /switch\s*1/.test(detail.replace(/\n/g, ' ')));
await snap(`11-device-detail`);

// Clean up so repeated runs stay idempotent.
page.on('dialog', (dialog) => dialog.accept());
await page.click('text=Hapus');
await page.waitForTimeout(2000);
check('device removed', new URL(page.url()).pathname === '/devices');

check('no page errors', errors.length === 0, errors.join(' | '));

const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
await browser.close();
process.exit(failed.length ? 1 : 0);

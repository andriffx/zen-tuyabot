import { chromium } from 'playwright';
import { snap } from './e2e-helpers.mjs';

const base = process.env.BASE_URL ?? 'http://localhost:5173';
const USER = process.env.SMOKE_USER ?? 'root';
const PASS = process.env.SMOKE_PASS ?? 'password-panjang';


const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 950 } });
const errors = [];
page.on('pageerror', (error) => errors.push(error.message));
page.on('console', (msg) => {
	if (msg.type() === 'error' && !/40[134] \(/.test(msg.text()) && !/ERR_FAILED/.test(msg.text()))
		errors.push(msg.text());
});

const results = [];
function check(name, ok, extra = '') {
	results.push({ name, ok: Boolean(ok) });
	console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${extra ? ` — ${extra}` : ''}`);
}

async function ensureSession() {
	await page.goto(base + '/', { waitUntil: 'networkidle' });
	await page.waitForTimeout(1200);
	if (new URL(page.url()).pathname === '/setup') {
		await page.fill('#username', USER);
		await page.fill('#password', PASS);
		await page.fill('#confirm', PASS);
		await page.click('button[type=submit]');
		await page.waitForTimeout(2000);
		await page.click('text=Lewati, buka dashboard');
		await page.waitForTimeout(2000);
	} else if (new URL(page.url()).pathname === '/login') {
		await page.fill('#username', USER);
		await page.fill('#password', PASS);
		await page.click('button[type=submit]');
		await page.waitForTimeout(2000);
	}
}

await ensureSession();

// ── Overview renders with real payloads ────────────────────────────────────
check('on dashboard', new URL(page.url()).pathname === '/');
const body = (await page.locator('body').innerText()).toLowerCase();
check('overview heading', body.includes('overview'));
check('tile: perangkat online', body.includes('perangkat online'));
check('tile: daya sekarang', body.includes('daya sekarang'));
check('tile: backup terakhir', body.includes('backup terakhir'));
check('tile: status sistem', body.includes('status sistem'));
check('device ratio rendered', /\d+\/\d+/.test(body), (body.match(/\d+\/\d+/) ?? [''])[0]);
check('system status reads ok/degraded', /ok|degraded|down/.test(body));
check('power chart empty state', body.includes('belum ada data daya'));
check('activity empty state', body.includes('belum ada aktivitas'));
check('no partial failure banner', !body.includes('sebagian data gagal dimuat'));
check('no leftover placeholder text', !body.includes('akan dibangun pada milestone'));
await snap(page, `20-overview`);

// ── A degraded state must surface as an alert ─────────────────────────────
// Simulate a dropped SSE by aborting the stream, then confirm the alert text.
await page.route('**/api/stream', (route) => route.abort());
await page.reload({ waitUntil: 'domcontentloaded' });
await page.waitForTimeout(3000);
const afterDrop = await page.locator('body').innerText();
check('realtime outage raises an alert', afterDrop.includes('Realtime terputus'));
check('realtime outage does not blank the page', afterDrop.includes('Overview'));
await snap(page, `21-overview-sse-down`);

check('no page errors', errors.length === 0, errors.join(' | '));

const failed = results.filter((result) => !result.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
await browser.close();
process.exit(failed.length ? 1 : 0);

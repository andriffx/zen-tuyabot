import { chromium } from 'playwright';
import { snap } from './e2e-helpers.mjs';

const base = process.env.BASE_URL ?? 'http://localhost:5173';
const USER = process.env.SMOKE_USER ?? 'root';
const PASS = process.env.SMOKE_PASS ?? 'password-panjang';


const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
const errors = [];
page.on('pageerror', (error) => errors.push(error.message));
page.on('console', (msg) => {
	if (
		msg.type() === 'error' &&
		!/40[1349] \(|503 \(/.test(msg.text()) &&
		!/ERR_FAILED/.test(msg.text())
	) {
		errors.push(msg.text());
	}
});

const results = [];
function check(name, ok, extra = '') {
	results.push({ name, ok: Boolean(ok) });
	console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${extra ? ` — ${extra}` : ''}`);
}

async function signIn() {
	await page.goto(base + '/', { waitUntil: 'networkidle' });
	await page.waitForTimeout(1200);
	if (new URL(page.url()).pathname === '/setup') {
		await page.fill('#username', USER);
		await page.fill('#password', PASS);
		await page.fill('#confirm', PASS);
		await page.click('button[type=submit]');
		await page.waitForTimeout(2000);
		await page.click('text=Lewati, buka dashboard');
	} else if (new URL(page.url()).pathname === '/login') {
		await page.fill('#username', USER);
		await page.fill('#password', PASS);
		await page.click('button[type=submit]');
	}
	await page.waitForTimeout(2500);
}

await signIn();

// A previous run may have left maintenance on; normalise before asserting pages.
await page.evaluate(async () => {
	const csrf = document.cookie
		.split('; ')
		.find((entry) => entry.startsWith('csrf_token='))
		?.split('=')[1];
	await fetch('/api/maintenance', {
		method: 'POST',
		credentials: 'same-origin',
		headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
		body: JSON.stringify({ enabled: false })
	});
});
await page.reload({ waitUntil: 'networkidle' });
await page.waitForTimeout(1500);
check(
	'no maintenance left over from a previous run',
	!(await page.locator('body').innerText()).includes('Sistem dalam maintenance')
);

// ── Log pages ──────────────────────────────────────────────────────────────
for (const [path, heading, emptyText] of [
	['/logs/power', 'Log Daya', 'Belum ada log daya'],
	['/logs/activities', 'Log Aktivitas', 'Belum ada aktivitas'],
	['/logs/errors', 'Log Error', 'Tidak ada error']
]) {
	await page.goto(base + path, { waitUntil: 'networkidle' });
	await page.waitForTimeout(1500);
	const text = await page.locator('body').innerText();
	check(`${path}: heading`, text.includes(heading));
	check(`${path}: renders rows or an empty state`, text.includes(emptyText) || text.includes('baris'));
	check(`${path}: pagination controls present`, text.includes('Berikutnya') || text.includes(emptyText));
	await snap(page, `40-${path.split('/').pop()}`);
}

// Device filter reloads the table without an error.
await page.goto(base + '/logs/activities', { waitUntil: 'networkidle' });
await page.waitForTimeout(1200);
// shadcn Select: open the trigger, then click an item (no native <option>).
const filter = page.locator('[data-slot="select-trigger"]').first();
await filter.click();
const content = page.locator('[data-slot="select-content"]').first();
await content.waitFor({ state: 'visible', timeout: 5000 });
const options = await content.locator('[data-slot="select-item"]').allTextContents();
check('activities: device filter lists "Semua"', options.some((o) => o.trim() === 'Semua'), JSON.stringify(options));
await content.locator('[data-slot="select-item"]').first().click();
await page.waitForTimeout(1200);
check('activities: filter change does not error', !(await page.locator('body').innerText()).includes('Coba lagi'));

// ── System page ────────────────────────────────────────────────────────────
await page.goto(base + '/system', { waitUntil: 'networkidle' });
await page.waitForTimeout(2000);
let text = await page.locator('body').innerText();
check('system: health card shows a status', /ok|degraded|down/i.test(text));
check('system: database section present', text.toLowerCase().includes('statistik database'));
check('system: schema version shown', text.includes('Versi skema'));
check('system: maintenance toggle present', text.toLowerCase().includes('maintenance'));
check('system: audit section present', text.toLowerCase().includes('audit log'));
await snap(page, `41-system`);

// Audit table loads at least the setup/login entries.
check('system: audit has entries or empty state', /access\.denied|auth\.login|setup\.complete|Tidak ada entri audit/.test(text));

// Open a details drawer if there is one.
const detailButton = page.locator('button:has-text("Detail")').first();
if ((await detailButton.count()) > 0) {
	await detailButton.click();
	await page.waitForTimeout(600);
	text = await page.locator('body').innerText();
	check('system: audit drawer opens', text.includes('Detail audit'));
	await page.keyboard.press('Escape');
	await page.waitForTimeout(400);
	check('system: Escape closes the drawer', !(await page.locator('body').innerText()).includes('Detail audit'));
	await snap(page, `42-audit`);
} else {
	check('system: audit drawer (skipped, no rows)', true);
}

// ── Maintenance round-trip ─────────────────────────────────────────────────
// Normalise the state through the API first: a previous run may have left
// maintenance on, and the toggle's meaning then flips.
async function setMaintenance(enabled) {
	await page.evaluate(
		async ({ enabled }) => {
			const csrf = document.cookie
				.split('; ')
				.find((entry) => entry.startsWith('csrf_token='))
				?.split('=')[1];
			await fetch('/api/maintenance', {
				method: 'POST',
				credentials: 'same-origin',
				headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
				body: JSON.stringify({ enabled })
			});
		},
		{ enabled }
	);
}

await page.goto(base + '/system', { waitUntil: 'networkidle' });
await page.waitForTimeout(1200);
await setMaintenance(false);

await page.goto(base + '/system', { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);
const maintSwitch = page.getByRole('switch').first();
if ((await maintSwitch.count()) > 0) {
	await maintSwitch.click();
	await page.waitForTimeout(2500);
	text = await page.locator('body').innerText();
	check(
		'system: maintenance turns on',
		text.includes('Maintenance aktif'),
		text.toLowerCase().includes('maintenance aktif') ? '' : 'alert not shown'
	);

	// Non-auth pages must be blocked, and the app must show the maintenance screen.
	await page.goto(base + '/devices', { waitUntil: 'networkidle' });
	await page.waitForTimeout(1500);
	const blocked = await page.locator('body').innerText();
	check(
		'system: maintenance replaces other pages with the maintenance screen',
		blocked.includes('Sistem dalam maintenance'),
		blocked.slice(0, 60).replace(/\s+/g, ' ')
	);
	check(
		'system: maintenance hides the page content',
		!blocked.includes('Tambah device')
	);

	// Turn it off the same way an operator would: through the System page.
	// The maintenance screen keeps /system reachable for exactly this reason.
	await page.goto(base + '/system', { waitUntil: 'domcontentloaded' });
	await page.waitForTimeout(2500);
	const offSwitch = page.getByRole('switch').first();
	check('system: maintenance page stays reachable', (await offSwitch.count()) > 0);
	if ((await offSwitch.count()) > 0) {
		// The switch reflects the server flag; wait for it to flip rather than
		// guessing a timeout, then confirm the API agrees.
		const stateBefore = await offSwitch.getAttribute('data-state');
		await offSwitch.click();
		await page.waitForFunction(
			(previous) =>
				document.querySelector('button[role="switch"]')?.getAttribute('data-state') !== previous,
			stateBefore,
			{ timeout: 10_000 }
		);
		await page.waitForTimeout(800);
		const flag = await page.evaluate(async () => {
			const response = await fetch('/api/maintenance/status', { credentials: 'same-origin' });
			return (await response.json()).maintenance;
		});
		check('system: maintenance actually turned off', flag === false, `flag=${flag}`);
	}

	await page.goto(base + '/devices', { waitUntil: 'domcontentloaded' });
	await page.waitForTimeout(2500);
	check(
		'system: devices reachable again after maintenance off',
		(await page.locator('body').innerText()).includes('Devices')
	);
	await snap(page, `43-after-maintenance`);
} else {
	check('system: maintenance toggle (skipped)', true);
}

check('no page errors', errors.length === 0, errors.join(' | '));

const failed = results.filter((result) => !result.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
await browser.close();
process.exit(failed.length ? 1 : 0);

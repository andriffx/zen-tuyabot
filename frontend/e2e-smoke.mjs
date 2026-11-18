import { chromium } from 'playwright';
import { snap } from './e2e-helpers.mjs';

/**
 * Manual browser smoke test for the Zen Tuyabot dashboard.
 *
 * Requires: a running backend (default 127.0.0.1:8080) and `npm run dev`.
 * Install the browser once:  npx playwright install chromium
 *
 * Usage:
 *   node e2e-smoke.mjs                       # against http://localhost:5173
 *   BASE_URL=http://localhost:4173 node e2e-smoke.mjs
 *
 * Exit code is 1 when any check fails, so it can be wired into a script later.
 */

const base = process.env.BASE_URL ?? 'http://localhost:5173';
const USER = process.env.SMOKE_USER ?? 'root';
const PASS = process.env.SMOKE_PASS ?? 'password-panjang';


const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await context.newPage();

const consoleErrors = [];
page.on('console', (msg) => {
	if (msg.type() === 'error') consoleErrors.push(msg.text());
});
page.on('pageerror', (error) => consoleErrors.push(`pageerror: ${error.message}`));

const results = [];
function check(name, condition, extra = '') {
	const ok = Boolean(condition);
	results.push({ name, ok });
	console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${extra ? ` — ${extra}` : ''}`);
}

async function shot(name) {
	await snap(page, `${name}`);
}

/**
 * A blank page or a framework error overlay must fail the run. HTTP 200 is not
 * evidence that the app rendered: Vite serves the shell even when the client
 * crashed on boot.
 */
async function assertAppRendered(label) {
	const overlay = await page.evaluate(() => {
		// Vite injects <vite-error-overlay>; SvelteKit adds an error page too.
		const viteOverlay = Boolean(document.querySelector('vite-error-overlay'));
		const bodyText = (document.body?.innerText ?? '').trim();
		return { viteOverlay, bodyTextLength: bodyText.length, head: bodyText.slice(0, 160) };
	});
	check(`${label}: no framework error overlay`, !overlay.viteOverlay);
	check(`${label}: page has visible content`, overlay.bodyTextLength > 20, originalText(overlay.head));
}

function originalText(value) {
	return value.replace(/\s+/g, ' ').slice(0, 80);
}

// ── 1. Fresh instance is gated to setup ────────────────────────────────────
await page.goto(base, { waitUntil: 'networkidle' });
await page.waitForTimeout(1200);
await assertAppRendered('setup page');
// The smoke test is idempotent: it accepts either a pristine instance (wizard
// shown) or an instance that was already set up by an earlier run (login shown).
const startedAtSetup = new URL(page.url()).pathname === '/setup';
check(
	'unset instance goes to setup, set-up instance goes to login',
	['/setup', '/login'].includes(new URL(page.url()).pathname),
	page.url()
);

if (startedAtSetup) {
	await shot('01-setup');
	check('setup form is present', await page.isVisible('#username'));

	// ── 2. Setup creates the first Superadmin ────────────────────────────────
	await page.fill('#username', USER);
	await page.fill('#password', PASS);
	await page.fill('#confirm', PASS);
	await page.click('button[type=submit]');
	await page.waitForTimeout(2000);
	check('setup reaches the follow-up step', await page.isVisible('text=Setup selesai'));
	await shot('02-setup-done');

	await page.click('text=Lewati, buka dashboard');
} else {
	console.log('NOTE  instance already set up — logging in instead of running the wizard');
	await shot('01-login');
	await page.fill('#username', USER);
	await page.fill('#password', PASS);
	await page.click('button[type=submit]');
}
await page.waitForTimeout(2500);
check('lands on dashboard', new URL(page.url()).pathname === '/', page.url());
check('overview heading visible', await page.isVisible('h1:has-text("Overview")'));

const navCount = await page.locator('[data-slot="sidebar-menu-button"]').count();
check('sidebar renders 12 entries', navCount === 12, `found ${navCount}`);

const navLabels = await page.locator('[data-slot="sidebar-menu-button"]').allInnerTexts();
check(
	'sidebar lists the expected pages',
	['Overview', 'Devices', 'Settings', 'Users', 'Roles', 'Bots', 'Backup', 'System'].every((label) =>
		navLabels.some((text) => text.includes(label))
	),
	navLabels.map((text) => text.trim()).join(', ')
);

check('API badge rendered', await page.isVisible('text=API'));
check('realtime badge rendered', await page.isVisible('text=Realtime'));
check('user menu present', await page.isVisible('button[aria-label="Akun"]'));
check('theme toggle present', await page.isVisible('button[aria-label="Tema"]'));
await page.waitForTimeout(1500); // let the success toast clear
await shot('03-dashboard');

// The SSE badge must actually become "connected", not merely exist.
await page.waitForFunction(
	() => !document.body.innerText.includes('Realtime terputus'),
	undefined,
	{ timeout: 8000 }
);
check('SSE stream connected', !(await page.isVisible('text=Realtime terputus')));

// ── 4. Devices page renders through the real API ───────────────────────────
await page.click('a[data-slot="sidebar-menu-button"][href="/devices"]');
await page.waitForTimeout(1500);
check('navigates to /devices', new URL(page.url()).pathname === '/devices', page.url());
check('devices heading visible', await page.isVisible('h1:has-text("Devices")'));
check(
	'devices page shows the empty state for a fresh install',
	await page.isVisible('text=Belum ada perangkat terdaftar')
);
await shot('04-devices');

// ── 5. Device create dialog opens (form renders, not a crash) ──────────────
await page.click('text=Tambah device pertama');
await page.waitForTimeout(700);
check('device dialog opens', await page.isVisible('#dev-name'));
check('DPS editor is prefilled from the template', (await page.inputValue('#dps-switch')) === '1');
await shot('05-device-dialog');
await page.keyboard.press('Escape');
await page.waitForTimeout(400);

// ── 6. Dark mode ───────────────────────────────────────────────────────────
await page.click('button[aria-label="Tema"]');
await page.waitForTimeout(300);
await page.click('text=Gelap');
await page.waitForTimeout(700);
check(
	'dark class applied to html',
	await page.evaluate(() => document.documentElement.classList.contains('dark'))
);
await shot('06-dark');

// ── 7. Logout ──────────────────────────────────────────────────────────────
await page.click('button[aria-label="Akun"]');
await page.waitForTimeout(400);
await page.click('text=Keluar');
await page.waitForTimeout(2000);
check('logout returns to /login', new URL(page.url()).pathname === '/login', page.url());
await shot('07-login');

// ── 8. Wrong password is an inline error, not a redirect loop ──────────────
await page.fill('#username', USER);
await page.fill('#password', 'salah-sekali');
await page.click('button[type=submit]');
await page.waitForTimeout(1500);
check('wrong password shows an inline error', await page.isVisible('text=Username atau password salah'));
check('wrong password does not navigate away', new URL(page.url()).pathname === '/login');

// ── 9. Correct login works ─────────────────────────────────────────────────
await page.fill('#password', PASS);
await page.click('button[type=submit]');
await page.waitForTimeout(2000);
check('login returns to the dashboard', new URL(page.url()).pathname === '/', page.url());

// ── 10. Anonymous reload stays on /login ───────────────────────────────────
const anon = await browser.newContext();
const anonPage = await anon.newPage();
await anonPage.goto(base + '/', { waitUntil: 'networkidle' });
await anonPage.waitForTimeout(1500);
check('anonymous reload goes to /login', new URL(anonPage.url()).pathname === '/login', anonPage.url());
await anon.close();

// ── 11. Fatal client errors fail the run ───────────────────────────────────
const fatal = consoleErrors.filter(
	(text) => !/409 \(Conflict\)|401 \(Unauthorized\)/.test(text)
);
check('no unexpected console errors', fatal.length === 0, fatal.join(' | '));

const failed = results.filter((result) => !result.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
await browser.close();
process.exit(failed.length ? 1 : 0);

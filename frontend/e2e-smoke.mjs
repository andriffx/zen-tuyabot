import { chromium } from 'playwright';

const base = 'http://localhost:5173';
const out = process.env.SHOT_DIR ?? '.';

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
const page = await context.newPage();

const errors = [];
page.on('console', (msg) => {
	if (msg.type() === 'error') errors.push(msg.text());
});
page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`));

const results = [];
function check(name, condition, extra = '') {
	results.push({ name, ok: Boolean(condition), extra });
	console.log(`${condition ? 'PASS' : 'FAIL'}  ${name}${extra ? ` — ${extra}` : ''}`);
}

async function shot(name) {
	await page.screenshot({ path: `${out}/${name}.png`, fullPage: true });
}

// 1. Fresh instance is gated to setup.
await page.goto(base + '/', { waitUntil: 'networkidle' });
await page.waitForTimeout(1200);
check('fresh instance redirects to /setup', new URL(page.url()).pathname === '/setup', page.url());
await shot('01-setup');

// 2. Setup creates the first Superadmin.
await page.fill('#username', 'root');
await page.fill('#password', 'password-panjang');
await page.fill('#confirm', 'password-panjang');
await page.click('button[type=submit]');
await page.waitForTimeout(2000);
check('setup shows the follow-up step', await page.isVisible('text=Setup selesai'));
await shot('02-setup-done');

// 3. Dashboard shell renders.
await page.click('text=Lewati, buka dashboard');
await page.waitForTimeout(2000);
check('lands on dashboard', new URL(page.url()).pathname === '/', page.url());
check('overview heading visible', await page.isVisible('h1:has-text("Overview")'));

const navCount = await page.locator('[data-slot="sidebar-menu-button"]').count();
check('sidebar renders 12 entries', navCount === 12, `found ${navCount}`);

check('connection badge shows API', await page.isVisible('text=API'));
check('user menu button present', await page.isVisible('button[aria-label="Akun"]'));
check('theme toggle present', await page.isVisible('button[aria-label="Tema"]'));
await page.waitForTimeout(1500); // let the toast settle before the screenshot
await shot('03-dashboard');

// 4. SSE badge: /api/stream should be connected.
const realtime = await page.locator('text=Realtime').first().textContent();
check('realtime badge rendered', Boolean(realtime), realtime ?? '');
await shot('04-header');

// 5. Dark mode toggles the html class.
await page.click('button[aria-label="Tema"]');
await page.waitForTimeout(300);
await page.click('text=Gelap');
await page.waitForTimeout(700);
const dark = await page.evaluate(() => document.documentElement.classList.contains('dark'));
check('dark class applied', dark);
await shot('05-dark');

// 6. Logout returns to login.
await page.click('button[aria-label="Akun"]');
await page.waitForTimeout(400);
await page.click('text=Keluar');
await page.waitForTimeout(2000);
check('logout returns to /login', new URL(page.url()).pathname === '/login', page.url());
await shot('06-login');

// 7. Login again works.
await page.fill('#username', 'root');
await page.fill('#password', 'password-panjang');
await page.click('button[type=submit]');
await page.waitForTimeout(2000);
check('login returns to dashboard', new URL(page.url()).pathname === '/', page.url());

// 8. Wrong password shows an error, not a redirect loop.
const second = await browser.newContext();
const page2 = await second.newPage();
await page2.goto(base + '/login', { waitUntil: 'networkidle' });
await page2.fill('#username', 'root');
await page2.fill('#password', 'salah-sekali');
await page2.click('button[type=submit]');
await page2.waitForTimeout(1500);
check(
	'wrong password shows inline error',
	await page2.isVisible('text=Username atau password salah')
);
await second.close();

// 9. Unauthenticated reload keeps the user on /login.
await page.close();
const anon = await browser.newContext();
const page3 = await anon.newPage();
await page3.goto(base + '/', { waitUntil: 'networkidle' });
await page3.waitForTimeout(1500);
check('anonymous reload goes to /login', new URL(page3.url()).pathname === '/login', page3.url());
await anon.close();

console.log('console errors:', errors.length ? errors : 'none');
const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
await browser.close();
process.exit(failed.length ? 1 : 0);

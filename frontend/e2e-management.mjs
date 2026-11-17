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

async function shot(name) {
	await snap(`${name}`);
}

// Sign in (setup if needed).
await page.goto(base + '/', { waitUntil: 'networkidle' });
await page.waitForTimeout(1200);
if (new URL(page.url()).pathname === '/setup') {
	await page.fill('#username', USER);
	await page.fill('#password', PASS);
	await page.fill('#confirm', PASS);
	await page.click('button[type=submit]');
	await page.waitForTimeout(2000);
	await page.click('text=Lewati, buka dashboard');
} else {
	await page.fill('#username', USER);
	await page.fill('#password', PASS);
	await page.click('button[type=submit]');
}
await page.waitForTimeout(2500);

// ── Settings ───────────────────────────────────────────────────────────────
await page.goto(base + '/settings', { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);
let text = (await page.locator('body').innerText()).toLowerCase();
check('settings: groups render', text.includes('monitoring') && text.includes('backup'));
check('settings: apply badge present', text.includes('langsung') || text.includes('restart bot'));
check('settings: read-only system keys marked', text.includes('khusus sistem'));
const input = page.locator('[id="setting-monitoring.power_interval_minutes"]');
check('settings: numeric field present', (await input.count()) === 1);

// Always pick a value different from the current one so repeated runs stay valid.
const current = Number(await input.inputValue());
const next = current === 7 ? 8 : 7;
await input.fill(String(next));
await page.waitForTimeout(600);
check(
	'settings: field reflects the typed value',
	Number(await input.inputValue()) === next,
	`${current} -> ${await input.inputValue()}`
);
check('settings: save bar reports a change', (await page.locator('body').innerText()).includes('1 setting berubah'));
await page.locator('div.fixed button:has-text("Simpan")').click();
await page.waitForTimeout(2500);
text = (await page.locator('body').innerText()).toLowerCase();
check('settings: save succeeded', text.includes('tersimpan'));
await shot('30-settings');

// ── Roles ──────────────────────────────────────────────────────────────────
await page.goto(base + '/roles', { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);
text = (await page.locator('body').innerText());
check('roles: seeded roles listed', /superadmin/i.test(text) && /operator/i.test(text));
check('roles: protected badge shown', /terlindungi/i.test(text));
check('roles: user counts shown', /pemakai/i.test(text));
await shot('31-roles');

// Open the superadmin role editor: protected keys must be locked.
const superadminCard = page.locator('[data-slot="card"]', { hasText: 'Superadmin' }).first();
await superadminCard.getByText(/Ubah izin|Lihat izin/).click();
await page.waitForTimeout(1500);
text = await page.locator('body').innerText();
check('roles: permission matrix groups render', /perangkat/i.test(text) && /sistem/i.test(text));
check('roles: permission keys shown in mono', /devices\.view/.test(text));
const lockedBoxes = await page.locator('button[role="checkbox"][disabled]').count();
check('roles: protected keys are disabled', lockedBoxes > 0, `${lockedBoxes} disabled`);
await shot('32-role-editor');

// Edit the OPERATOR role, not superadmin: saving a role revokes its sessions,
// and revoking a permission from the account running the test would lock it out.
await page.goto(base + '/roles', { waitUntil: 'networkidle' });
await page.waitForTimeout(1200);
const operatorCard = page.locator('[data-slot="card"]', { hasText: 'Operator' }).first();
await operatorCard.getByText(/Ubah izin|Lihat izin/).click();
await page.waitForTimeout(1500);

const candidate = page
	.locator('label:has(.font-mono):has(button[role="checkbox"]:not([disabled])[data-state="checked"])')
	.last();
const candidateKey = (await candidate.locator('.font-mono').first().innerText()).trim();
await candidate.locator('button[role="checkbox"]').click();
await page.waitForTimeout(500);
check(
	'roles: edit enables save',
	await page.isEnabled('button:has-text("Simpan izin")'),
	`revoked ${candidateKey} from operator`
);
await page.click('button:has-text("Simpan izin")');
await page.waitForTimeout(2500);
check(
	'roles: saving another role keeps the editor signed in',
	new URL(page.url()).pathname.startsWith('/roles'),
	page.url()
);

// ── Users ──────────────────────────────────────────────────────────────────
await page.goto(base + '/users', { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);
text = await page.locator('body').innerText();
check('users: page loads', /akun web/i.test(text));
check('users: empty state or table', /belum ada akun/i.test(text) || /username/i.test(text));
await shot('33-users');

// ── Telegram users ─────────────────────────────────────────────────────────
await page.goto(base + '/telegram-users', { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);
text = await page.locator('body').innerText();
check('telegram users: page loads', /identitas bot/i.test(text));
check('telegram users: empty state', /belum ada user telegram/i.test(text));

await page.click('button:has-text("Daftarkan")');
await page.waitForTimeout(600);
await page.fill('#tg-id', '123456789');
await page.fill('#tg-label', 'Budi');
await page.click('button[type=submit]:has-text("Daftarkan")');
await page.waitForTimeout(2500);
text = await page.locator('body').innerText();
check('telegram users: row created', text.includes('123456789') && text.includes('Budi'));
await shot('34-telegram-users');

// ── Bots ───────────────────────────────────────────────────────────────────
await page.goto(base + '/bots', { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);
text = await page.locator('body').innerText();
check('bots: empty state', /belum ada bot telegram/i.test(text));

await page.click('button:has-text("Tambah bot")');
await page.waitForTimeout(600);
await page.fill('#bot-label', 'produksi');
await page.fill('#bot-token', '123456:AAFakeTokenForSmokeTest');
await page.click('button[type=submit]:has-text("Simpan")');
await page.waitForTimeout(2000);
text = await page.locator('body').innerText();
check('bots: card created', text.includes('produksi'));
check('bots: token value never rendered', !text.includes('AAFakeTokenForSmokeTest'));
check('bots: starts disabled', /nonaktif/i.test(text));
await shot('35-bots');

// Enabling with a fake token must surface an error, not hang.
await page.locator('[data-slot="switch"]').first().click();
await page.waitForTimeout(4000);
text = await page.locator('body').innerText();
check('bots: invalid token recorded as error', /error terakhir/i.test(text) || /token/i.test(text));
await shot('36-bots-error');

check('no page errors', errors.length === 0, errors.join(' | '));

const failed = results.filter((result) => !result.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
await browser.close();
process.exit(failed.length ? 1 : 0);

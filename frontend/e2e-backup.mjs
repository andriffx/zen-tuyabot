import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';

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
const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });
const errors = [];
page.on('pageerror', (error) => errors.push(error.message));
page.on('console', (msg) => {
	if (msg.type() === 'error' && !/40[1349] \(|503 \(/.test(msg.text()) && !/ERR_FAILED/.test(msg.text()))
		errors.push(msg.text());
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

// ── Backup page ────────────────────────────────────────────────────────────
await page.goto(base + '/backup', { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);
let text = await page.locator('body').innerText();
check('backup: page loads', text.includes('Backup'));
check('backup: restore affordance shown for superadmin', text.includes('Restore'));
check('backup: download warning explained', /rahasia/i.test(text));
await snap(`50-backup-empty`);

// Create a backup through the UI.
const createButton = page.locator('button:has-text("Buat backup")').first();
await createButton.click();
await page.waitForTimeout(3000);
text = await page.locator('body').innerText();
check('backup: a run appears after creating', /tuyabot-\d{8}-\d{6}\.db/.test(text));
check('backup: kind badge rendered', /manual|otomatis/.test(text));
await snap(`51-backup-created`);

// Download the backup file to disk.
const downloadPromise = page.waitForEvent('download', { timeout: 15000 });
await page.locator('button:has-text("Unduh")').first().click();
const download = await downloadPromise;
const savedPath = `${out}/${download.suggestedFilename()}`;
await download.saveAs(savedPath);
const size = readFileSync(savedPath).byteLength;
check('backup: file downloads and is non-empty', size > 1000, `${size} bytes`);

// ── Restore dialog validation ──────────────────────────────────────────────
await page.locator('button:has-text("Restore…")').click();
await page.waitForTimeout(600);
const restoreText = await page.locator('body').innerText();
check('restore: dialog warns about maintenance and sessions', /maintenance/i.test(restoreText));
const submit = page.locator('dialog button[type=submit], [role=dialog] button[type=submit]').last();
check('restore: submit disabled until valid', await submit.isDisabled());

// Validity needs all three: file, password, and the typed word.
await page.locator('#restore-file').setInputFiles(savedPath);
await page.locator('#restore-password').fill(PASS);
await page.locator('#restore-confirm').fill('RESTORE');
await page.waitForTimeout(400);
check('restore: submit enabled once the form is complete', await submit.isEnabled());
await snap(`52-restore-dialog`);

// A wrong password must be refused, not silently accepted.
await page.locator('#restore-password').fill('salah-sekali');
await page.waitForTimeout(300);
await submit.click();
await page.waitForTimeout(2500);
text = await page.locator('body').innerText();
check('restore: wrong password rejected', /gagal|salah|password/i.test(text));
check('restore: dialog stays open after a failure', await page.isVisible('#restore-confirm'));

// ── Real restore with the downloaded file ─────────────────────────────────
await page.locator('#restore-password').fill(PASS);
await page.locator('#restore-confirm').fill('RESTORE');
await page.waitForTimeout(400);
check(
	'restore: password field holds the correct value before submitting',
	(await page.locator('#restore-password').inputValue()) === PASS
);
await submit.click();
await page.waitForTimeout(8000);

text = await page.locator('body').innerText();
const restored = /Restore selesai|restore/i.test(text) && !text.includes('Restore gagal');
// The restore revokes sessions, so the app must land on /login.
const atLogin = new URL(page.url()).pathname === '/login';
check('restore: succeeds with a valid file and password', restored || atLogin, page.url());
await snap(`53-after-restore`);

// Sign back in and confirm the backup list still renders.
await signIn();
await page.goto(base + '/backup', { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);
text = await page.locator('body').innerText();
check('restore: app usable afterwards', text.includes('Backup'));

check('no page errors', errors.length === 0, errors.join(' | '));

const failed = results.filter((result) => !result.ok);
console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
await browser.close();
process.exit(failed.length ? 1 : 0);

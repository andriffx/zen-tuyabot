/**
 * Shared helpers for the manual e2e suites.
 *
 * Screenshots are opt-in: with SHOT_DIR unset nothing is written, so a normal
 * run leaves the working tree clean (they are for manual reports, not the repo).
 */
const out = process.env.SHOT_DIR ?? null;

export async function snap(page, name, fullPage = true) {
	if (!out) return;
	await page.screenshot({ path: `${out}/${name}.png`, fullPage });
}

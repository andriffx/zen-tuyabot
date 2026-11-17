import { describe, expect, it } from 'vitest';
import { backupForm, restoreStageText } from './backup-form';

describe('backupForm.restore', () => {
	it('requires a password and the literal RESTORE', () => {
		const form = backupForm.restore();
		expect(form.valid).toBe(false);

		form.setFile(new File(['x'], 'a.db'));
		form.setPassword('rahasia');
		form.setConfirm('bukan');
		expect(form.valid).toBe(false);

		form.setConfirm('restore');
		expect(form.valid).toBe(true);
		expect(form.toFormData().get('confirm')).toBe('RESTORE');
	});

	it('is invalid without a file', () => {
		const form = backupForm.restore();
		form.setPassword('rahasia');
		form.setConfirm('RESTORE');
		expect(form.valid).toBe(false);
	});

	it('refuses a file over 200 MB before uploading', () => {
		const form = backupForm.restore();
		const oversized = { size: 201 * 1024 * 1024 } as File;
		expect(form.setFile(oversized)).toBe('Ukuran file maksimal 200 MB');
		expect(form.file).toBeNull();
		expect(form.error).toBe('Ukuran file maksimal 200 MB');
	});

	it('accepts a file at the limit', () => {
		const form = backupForm.restore();
		const atLimit = { size: 200 * 1024 * 1024 } as File;
		expect(form.setFile(atLimit)).toBeNull();
		expect(form.file).toBe(atLimit);
	});

	it('normalises the confirmation and password into the payload', () => {
		const form = backupForm.restore();
		form.setFile(new File(['x'], 'a.db'));
		form.setPassword('  rahasia  ');
		form.setConfirm('  restore  ');
		const data = form.toFormData();
		expect(data.get('confirm')).toBe('RESTORE');
		expect(data.get('password')).toBe('  rahasia  ');
	});

	it('reset clears everything', () => {
		const form = backupForm.restore();
		form.setFile(new File(['x'], 'a.db'));
		form.setPassword('rahasia');
		form.setConfirm('RESTORE');
		form.reset();
		expect(form.valid).toBe(false);
		expect(form.file).toBeNull();
		expect(form.password).toBe('');
	});
});

describe('restoreStageText', () => {
	it('explains every stage the backend can return', () => {
		for (const stage of ['upload', 'integrity', 'schema', 'version', 'swap']) {
			expect(restoreStageText[stage]).toBeTruthy();
		}
	});
});

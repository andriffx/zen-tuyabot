export type RestoreForm = {
	readonly file: File | null;
	readonly password: string;
	readonly confirm: string;
	readonly error: string | null;
	readonly valid: boolean;
	setFile: (file: File | null) => string | null;
	setPassword: (value: string) => void;
	setConfirm: (value: string) => void;
	toFormData: () => FormData;
	reset: () => void;
};

const MAX_BYTES = 200 * 1024 * 1024;

/**
 * Restore requires a file, the current password, and the literal RESTORE.
 *
 * The size cap is checked here so an oversized upload fails before it leaves
 * the browser; the server would reject it anyway, but only after transferring.
 */
export const backupForm = {
	restore(): RestoreForm {
		let file: File | null = null;
		let password = '';
		let confirm = '';
		let error: string | null = null;

		const isValid = () => Boolean(file) && password.length > 0 && confirm.trim().toUpperCase() === 'RESTORE';

		return {
			get file() {
				return file;
			},
			get password() {
				return password;
			},
			get confirm() {
				return confirm;
			},
			get error() {
				return error;
			},
			get valid() {
				return isValid();
			},

			setFile(next) {
				if (next && next.size > MAX_BYTES) {
					error = 'Ukuran file maksimal 200 MB';
					file = null;
					return error;
				}
				error = null;
				file = next;
				return null;
			},

			setPassword(value) {
				password = value;
			},

			setConfirm(value) {
				confirm = value;
			},

			toFormData() {
				const form = new FormData();
				if (file) form.set('file', file);
				form.set('password', password);
				form.set('confirm', confirm.trim().toUpperCase());
				return form;
			},

			reset() {
				file = null;
				password = '';
				confirm = '';
				error = null;
			}
		};
	}
};

/** Indonesian text for the backend's restore failure stages. */
export const restoreStageText: Record<string, string> = {
	upload: 'File backup tidak dapat dibaca. Pilih ulang file.',
	integrity: 'File backup rusak atau bukan database yang valid.',
	schema: 'Struktur file tidak dikenali sebagai database Zen Tuyabot.',
	version: 'Backup berasal dari versi aplikasi yang lebih baru. Perbarui aplikasi dulu.',
	swap: 'Gagal menukar database. Database lama tetap utuh.'
};

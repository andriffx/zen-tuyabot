import { api, download as downloadBlob, get, post } from './client';
import type { BackupRun, RestoreResult } from './types';

export const backupApi = {
	list: () => get<{ backups: BackupRun[] }>('/api/backup'),
	create: () => post<{ id: number; filename: string; path: string; size_bytes: number }>('/api/backup'),
	download: (id: number, filename: string) => downloadBlob(`/api/backup/${id}/download`, filename),
	restore: (form: FormData) =>
		api<RestoreResult>('/api/backup/restore', { method: 'POST', form })
};

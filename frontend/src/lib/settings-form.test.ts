import { describe, expect, it } from 'vitest';
import type { SettingsSchemaEntry } from '#lib/api/types';
import { settingsForm } from './settings-form';

const schema: SettingsSchemaEntry[] = [
	{
		key: 'a.x',
		category: 'monitoring',
		type: 'int',
		default: 1,
		label: 'X',
		help: '',
		apply: 'live',
		secret: false,
		edit_permission: 'settings.edit',
		minimum: 0,
		maximum: 10,
		choices: [],
		read_only: false
	},
	{
		key: 'b.y',
		category: 'backup',
		type: 'bool',
		default: true,
		label: 'Y',
		help: '',
		apply: 'live',
		secret: false,
		edit_permission: 'settings.edit',
		minimum: null,
		maximum: null,
		choices: [],
		read_only: false
	},
	{
		key: 'a.z',
		category: 'monitoring',
		type: 'string',
		default: 'q',
		label: 'Z',
		help: '',
		apply: 'live',
		secret: false,
		edit_permission: 'settings.edit',
		minimum: null,
		maximum: null,
		choices: [],
		read_only: false
	},
	{
		key: 'sys.v',
		category: 'system',
		type: 'int',
		default: 9,
		label: 'V',
		help: '',
		apply: 'live',
		secret: false,
		edit_permission: 'settings.edit',
		minimum: null,
		maximum: null,
		choices: [],
		read_only: true
	},
	{
		key: 'ui.theme',
		category: 'ui',
		type: 'enum',
		default: 'system',
		label: 'Tema',
		help: '',
		apply: 'live',
		secret: false,
		edit_permission: 'settings.edit',
		minimum: null,
		maximum: null,
		choices: ['system', 'light', 'dark'],
		read_only: false
	}
];

describe('settingsForm', () => {
	it('groups by category in registry order', () => {
		const form = settingsForm.fromSchema(schema, {});
		expect(form.groups.map((group) => group.name)).toEqual([
			'Monitoring',
			'Backup',
			'Sistem',
			'Tampilan'
		]);
		expect(form.groups[0].fields.map((field) => field.key)).toEqual(['a.x', 'a.z']);
	});

	it('sends only changed, writable values', () => {
		const form = settingsForm.fromSchema(schema, { 'a.x': 1, 'sys.v': 9 });
		form.set('a.x', 7);
		form.set('sys.v', 10);
		expect(form.toPayload()).toEqual({ 'a.x': 7 });
		expect(form.dirty).toEqual(['a.x']);
	});

	it('ignores writes to read-only settings', () => {
		const form = settingsForm.fromSchema(schema, { 'sys.v': 9 });
		form.set('sys.v', 42);
		expect(form.toPayload()).toEqual({});
	});

	it('validates ranges before sending', () => {
		const form = settingsForm.fromSchema(schema, { 'a.x': 1 });
		form.set('a.x', 11);
		expect(form.validate()).toEqual([{ key: 'a.x', message: 'Maksimal 10' }]);

		form.set('a.x', -1);
		expect(form.validate()).toEqual([{ key: 'a.x', message: 'Minimal 0' }]);
	});

	it('rejects non-integers and non-numbers', () => {
		const form = settingsForm.fromSchema(schema, { 'a.x': 1 });
		form.set('a.x', 2.5);
		expect(form.validate()).toEqual([{ key: 'a.x', message: 'Harus bilangan bulat' }]);

		form.set('a.x', 'teks');
		expect(form.validate()).toEqual([{ key: 'a.x', message: 'Harus angka' }]);
	});

	it('validates enum choices', () => {
		const form = settingsForm.fromSchema(schema, { 'ui.theme': 'system' });
		form.set('ui.theme', 'neon');
		expect(form.validate()).toEqual([
			{ key: 'ui.theme', message: 'Pilih salah satu: system, light, dark' }
		]);
	});

	it('maps server errors without losing edits', () => {
		const form = settingsForm.fromSchema(schema, { 'a.x': 1 });
		form.set('a.x', 5);
		form.setFieldErrors([{ key: 'a.x', message: 'ditolak server' }]);
		expect(form.fields.find((field) => field.key === 'a.x')?.error).toBe('ditolak server');
		expect(form.toPayload()).toEqual({ 'a.x': 5 });
	});

	it('clears an error when the value is edited again', () => {
		const form = settingsForm.fromSchema(schema, { 'a.x': 1 });
		form.setFieldErrors([{ key: 'a.x', message: 'ditolak' }]);
		form.set('a.x', 3);
		expect(form.fields.find((field) => field.key === 'a.x')?.error).toBeUndefined();
	});

	it('never sends a secret back unless a replacement was typed', () => {
		const secretSchema: SettingsSchemaEntry[] = [
			{
				key: 'telegram.bot_token',
				category: 'telegram',
				type: 'secret',
				default: '',
				label: 'Token',
				help: '',
				apply: 'telegram_restart',
				secret: true,
				edit_permission: 'settings.edit',
				minimum: null,
				maximum: null,
				choices: [],
				read_only: false
			}
		];
		const form = settingsForm.fromSchema(secretSchema, {
			'telegram.bot_token': { has_value: true }
		});

		expect(form.toPayload()).toEqual({});

		form.set('telegram.bot_token', 'token-baru');
		expect(form.toPayload()).toEqual({ 'telegram.bot_token': 'token-baru' });
	});

	it('reset restores the initial values', () => {
		const form = settingsForm.fromSchema(schema, { 'a.x': 1 });
		form.set('a.x', 8);
		expect(form.dirty).toEqual(['a.x']);
		form.reset();
		expect(form.dirty).toEqual([]);
		expect(form.toPayload()).toEqual({});
	});
});

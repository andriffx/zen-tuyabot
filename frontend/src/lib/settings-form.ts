import type { FieldError } from '#lib/api/errors';
import type { SettingsSchemaEntry } from '#lib/api/types';

export type SettingField = SettingsSchemaEntry & { value: unknown; error?: string };

export type SettingGroup = { name: string; fields: SettingField[] };

export type SettingsForm = {
	groups: SettingGroup[];
	fields: SettingField[];
	/** Keys whose value differs from the value the form was built with. */
	get dirty(): string[];
	set: (key: string, value: unknown) => void;
	toPayload: () => Record<string, unknown>;
	validate: () => FieldError[];
	setFieldErrors: (errors: FieldError[]) => void;
	reset: () => void;
};

const CATEGORY_LABELS: Record<string, string> = {
	telegram: 'Telegram',
	monitoring: 'Monitoring',
	housekeeping: 'Housekeeping',
	backup: 'Backup',
	tuya: 'Tuya',
	security: 'Keamanan',
	maintenance: 'Maintenance',
	ui: 'Tampilan',
	system: 'Sistem'
};

export function categoryLabel(category: string): string {
	return CATEGORY_LABELS[category] ?? category;
}

function isSame(a: unknown, b: unknown): boolean {
	return JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
}

/**
 * Build a form model from the settings schema and current values.
 *
 * Secrets arrive as `{ has_value: true }`, never as text: they are excluded
 * from the payload unless the operator typed a replacement, so saving an
 * unrelated field cannot erase a stored token.
 */
export const settingsForm = {
	fromSchema(schema: SettingsSchemaEntry[], values: Record<string, unknown>): SettingsForm {
		const fields = schema.map<SettingField>((entry) => ({
			...entry,
			value: values[entry.key] ?? entry.default
		}));

		const initial = new Map(fields.map((field) => [field.key, field.value]));

		const groups: SettingGroup[] = [];
		for (const field of fields) {
			const name = categoryLabel(field.category);
			let group = groups.find((entry) => entry.name === name);
			if (!group) {
				group = { name, fields: [] };
				groups.push(group);
			}
			group.fields.push(field);
		}

		function dirtyKeys(): string[] {
			return fields
				.filter(
					(field) =>
						!field.read_only && !field.secret && !isSame(field.value, initial.get(field.key))
				)
				.map((field) => field.key);
		}

		return {
			groups,
			fields,

			get dirty() {
				return dirtyKeys();
			},

			set(key, value) {
				const field = fields.find((entry) => entry.key === key);
				if (!field || field.read_only) return;
				field.value = value;
				field.error = undefined;
			},

			toPayload() {
				const payload: Record<string, unknown> = {};
				for (const key of dirtyKeys()) {
					const field = fields.find((entry) => entry.key === key);
					if (field) payload[key] = field.value;
				}
				for (const field of fields) {
					if (field.secret && typeof field.value === 'string' && field.value.length > 0) {
						payload[field.key] = field.value;
					}
				}
				return payload;
			},

			validate() {
				const errors: FieldError[] = [];
				for (const field of fields) {
					if (field.read_only) continue;

					if (field.type === 'int' || field.type === 'float') {
						if (typeof field.value !== 'number' || Number.isNaN(field.value)) {
							errors.push({ key: field.key, message: 'Harus angka' });
							continue;
						}
						if (field.type === 'int' && !Number.isInteger(field.value)) {
							errors.push({ key: field.key, message: 'Harus bilangan bulat' });
							continue;
						}
						if (field.minimum !== null && field.value < field.minimum) {
							errors.push({ key: field.key, message: `Minimal ${field.minimum}` });
							continue;
						}
						if (field.maximum !== null && field.value > field.maximum) {
							errors.push({ key: field.key, message: `Maksimal ${field.maximum}` });
						}
					}

					if (field.type === 'enum' && !field.choices.includes(String(field.value))) {
						errors.push({
							key: field.key,
							message: `Pilih salah satu: ${field.choices.join(', ')}`
						});
					}
				}
				return errors;
			},

			setFieldErrors(errors) {
				for (const error of errors) {
					const field = fields.find((entry) => entry.key === error.key);
					if (field) field.error = error.message;
				}
			},

			reset() {
				for (const field of fields) {
					field.value = initial.get(field.key);
					field.error = undefined;
				}
			}
		};
	}
};

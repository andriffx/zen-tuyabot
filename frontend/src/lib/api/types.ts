/** Payload types, transcribed from the backend routes (verified contract). */

export type AuthMe = {
	id: number | null;
	username: string | null;
	actor_kind: 'web' | 'api_key' | 'telegram' | 'system';
	role: { id: number; slug: string; name: string } | null;
	permissions: string[];
	csrf_token: string | null;
};

export type SetupStatus = { required: boolean; steps_done: { admin: boolean } };
export type LoginResponse = { authenticated: boolean; user_id: number; csrf_token: string };

export type DeviceType = 'plug' | 'bulb' | 'switch' | 'sensor';

export type Device = {
	id: number;
	name: string;
	label: string;
	type: DeviceType;
	ip: string | null;
	version: number;
	dps: Record<string, number>;
	features: Record<string, boolean>;
	access_roles: number[];
	is_active: boolean;
	sort_order: number;
	last_seen_at: string | null;
	last_error: string | null;
	has_local_key: boolean;
};

export type DeviceTemplates = {
	templates: Record<DeviceType, Record<string, number>>;
	types: DeviceType[];
	features: string[];
};

export type DeviceStatus = {
	id: number;
	name: string;
	success: boolean;
	online: boolean;
	switch_on?: boolean | null;
	power_w?: number | null;
	current_a?: number | null;
	voltage_v?: number | null;
	age_seconds?: number | null;
	message?: string;
};

export type DeviceTestResult = {
	success: boolean;
	message?: string;
	raw?: Record<string, unknown>;
	mapped?: Record<string, unknown>;
	dps?: Record<string, number>;
};

export type DeviceDiagnosis = {
	device: {
		name: string | null;
		ip: string | null;
		tuya_id: string | null;
		version: number | string | null;
		has_local_key: boolean;
	};
	container: { addresses: string[] };
	checks: { name: string; target: string; ok: boolean; detail: string }[];
	hints: string[];
};

export type ControlResult = {
	success: boolean;
	message: string;
	device_id: number;
	state: boolean | null;
};

export type ScanCandidate = {
	ip: string;
	tuya_id: string | null;
	version: number | null;
	product_key: string | null;
	name: string | null;
};

export type ScanJob = {
	job_id: string;
	status: 'running' | 'done' | 'error';
	candidates: ScanCandidate[];
	error: string | null;
};

export type LogPage<T> = { items: T[]; limit?: number; offset?: number };

export type PowerLog = {
	id: number;
	device_id: number;
	device_name: string | null;
	device_label: string | null;
	power_w: number;
	voltage_v: number;
	current_a: number;
	switch_state: number | null;
	source: string;
	created_at: string;
};

export type ActivityLog = {
	id: number;
	device_id: number | null;
	device_name: string | null;
	device_label: string | null;
	user_id: number | null;
	actor: string;
	bot_id: number | null;
	action: string;
	status: string;
	message: string | null;
	created_at: string;
};

export type ErrorLog = {
	id: number;
	level: string;
	logger_name: string;
	message: string;
	exception_trace: string | null;
	file_name: string | null;
	line_number: number | null;
	created_at: string;
};

export type SettingType = 'string' | 'int' | 'float' | 'bool' | 'json' | 'secret' | 'enum';

export type SettingsSchemaEntry = {
	key: string;
	type: SettingType;
	default: unknown;
	category: string;
	label: string;
	help: string;
	apply: 'live' | 'telegram_restart';
	secret: boolean;
	edit_permission: string;
	minimum: number | null;
	maximum: number | null;
	choices: string[];
	read_only: boolean;
};

export type SettingsResponse = {
	values: Record<string, unknown>;
	schema: SettingsSchemaEntry[];
};

export type Role = {
	id: number;
	slug: string;
	name: string;
	description: string | null;
	permissions: string[];
	rate_limit_per_minute: number | null;
	is_system: number;
	is_protected: number;
	user_count: number;
};

export type PermissionCategory = { name: string; permissions: string[] };
export type PermissionCatalog = { categories: PermissionCategory[]; all: string[] };

export type WebUser = {
	id: number;
	username: string;
	role_id: number;
	is_active: number;
	created_by: number | null;
	created_at: string;
	updated_at: string;
	last_login_at: string | null;
	role: { id: number; slug: string; name: string };
};

export type TelegramUser = {
	telegram_id: number;
	label: string | null;
	role_id: number;
	is_active: number;
	role_slug: string;
	role_name: string;
	created_at: string;
	updated_at: string;
	last_seen_at: string | null;
};

export type Bot = {
	id: number;
	label: string;
	enabled: boolean;
	bot_username: string | null;
	last_ok_at: string | null;
	last_error: string | null;
	runtime_status: string;
};

export type BotTestResult = { ok: boolean; username?: string; message?: string };

export type BackupRun = {
	id: number;
	filename: string;
	size_bytes: number;
	kind: 'auto' | 'manual' | 'pre_restore';
	note: string | null;
	created_at: string;
};

export type RestoreResult = {
	restored: boolean;
	from_version: number;
	schema_version: number;
	pre_restore_backup: string;
};

export type Stats = {
	devices: { total: number; online: number; offline: number };
	rows: Record<string, number>;
	database: { path: string; size_bytes: number; schema_version: number };
	backup: { last: string | null; last_at: string | null };
	process: { pid: number };
};

export type Health = {
	status: 'ok' | 'degraded' | 'down';
	database: boolean;
	devices_total: number;
	devices_fresh: number;
	maintenance: boolean;
};

export type MaintenanceState = {
	maintenance: boolean;
	state?: { on: boolean; reason: string | null; auto_off_at: string | null };
};

export type AuditEntry = {
	id: number;
	at: string;
	actor_kind: string;
	actor_id: number | null;
	actor_label: string | null;
	action: string;
	target_kind: string | null;
	target_id: string | null;
	result: string;
	ip: string | null;
	details: Record<string, unknown> | null;
	request_id: string | null;
};

export type StreamDevice = {
	id: number;
	name: string;
	label: string;
	online: boolean;
	switch_on: boolean | null;
	power_w: number | null;
	voltage_v: number | null;
	current_a: number | null;
	age_seconds: number | null;
};

export type StreamSnapshot = { ts: number; devices: StreamDevice[] };

export type SessionRow = {
	token_hash: string;
	created_at: string;
	expires_at: string;
	last_seen_at: string;
	ip: string | null;
	user_agent: string | null;
	revoked_at: string | null;
	is_current: boolean;
};

export type RoleDeviceAccess = {
	device_id: number;
	can_view: boolean;
	can_on: boolean;
	can_off: boolean;
};

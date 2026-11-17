# Zen Tuyabot Frontend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the dashboard SPA that drives the existing Zen Tuyabot backend: setup wizard, login, devices, logs, settings, users, roles, bots, backup, and system pages behind a sidebar shell.

**Architecture:** SvelteKit with SSR disabled (pure SPA, `adapter-static` + `index.html` fallback). One `api/` client module owns every HTTP concern — cookie credentials, the CSRF header, error normalization. Auth and permission state live in a runes store hydrated from `GET /api/auth/me`; the router guard redirects on 401 (login), 409 (setup), 503 (maintenance). Vite proxies `/api` to the backend in dev; nginx proxies it in production, so cookies stay same-origin everywhere.

**Tech Stack:** SvelteKit 3.x, Svelte 5 (runes), TypeScript, Tailwind CSS 4, shadcn-svelte 1.x, mode-watcher (theme), svelte-sonner (toasts), Vitest + @testing-library/svelte, svelte-check.

**Spec:** `backend/docs/superpowers/specs/2026-11-17-tuyabot-rebuild-design.md` (sections §7.2, §8.15, §8.16)

## Global Constraints

- Monorepo root is `zen-tuyabot/`; this plan writes only inside `frontend/`.
- The backend is required. Do not build a mock server or MSW. If `/api` is unreachable the UI must show an error, not fake data.
- Node 24, npm 11. No pnpm, no yarn.
- Svelte 5 runes only (`$state`, `$derived`, `$effect`). No `export let`, no stores-from-svelte/store for new code.
- UI copy is Indonesian with English technical terms kept as-is: "Settings", "Backup", "Role", "Permission", "Device", "Bot", "Restore", "Maintenance", "Audit log", "Scan", "DPS". Never translate API field names.
- Every mutating request (POST/PATCH/DELETE) sends `X-CSRF-Token` read from the auth store, which gets it from `/api/auth/me` or the login/setup response.
- Never store credentials or the session token in `localStorage`. The session is an `HttpOnly` cookie; the CSRF token lives in memory only.
- All API errors surface as a `ApiError` with `status`, `detail`, `fieldErrors`. Never render raw backend text into HTML.
- Paths are relative to the monorepo: `frontend/`, tests under `frontend/src/**/*.test.ts`.
- `npm run check` (svelte-check) and `npm run test` must pass at the end of every task.

## Review Focus

Failure modes implied by the spec and the backend contract, each pinned by a test in the named task:

1. **Backend down or restarting** — every page must show a clear connection error and a retry action, never an empty successful-looking screen. (Task 2)
2. **Session expires mid-use** — the next request returns 401; the app must clear auth state and land on `/login`, not loop or show half-rendered admin UI. (Task 3)
3. **Permission changes while logged in** — the backend revokes sessions on role edits; the UI must not keep showing forbidden actions after its permissions no longer include them. (Task 4)
4. **Maintenance mode turned on** — non-auth routes return 503 with `detail: "maintenance"`; the app must show the maintenance screen instead of error toasts on every page. (Task 4)
5. **CSRF token missing after reload** — a hard refresh drops in-memory state; the app must re-hydrate from `/api/auth/me` before the first mutation, or mutations fail 403 unpredictably. (Task 3)

---

### Task 1: Scaffold SvelteKit, Tailwind 4, shadcn-svelte, dev proxy

**Files:**
- Create: `frontend/package.json`, `frontend/svelte.config.js`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/.npmrc`
- Create: `frontend/src/app.html`, `frontend/src/app.css`, `frontend/src/routes/+layout.ts`, `frontend/src/routes/+layout.svelte`, `frontend/src/routes/+page.svelte`
- Create: `frontend/components.json`, `frontend/vitest.config.ts`, `frontend/src/lib/utils.ts`
- Create: `frontend/.env.example`
- Test: `frontend/src/lib/utils.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces: a running dev server on 5173 whose `/api/*` reaches the backend on 8080; `cn(...classes)` helper from `$lib/utils`; `npm run check`, `npm run test`, `npm run build` scripts.

- [ ] **Step 1: Create the project and install**

```bash
cd "D:/Datas/MyData/Project Repo/zen-tuyabot"
npx sv create frontend --template minimal --types ts --no-add-ons --install npm
cd frontend
npm i -D @sveltejs/adapter-static tailwindcss @tailwindcss/vite vitest @testing-library/svelte @testing-library/jest-dom jsdom svelte-check
npm i mode-watcher svelte-sonner
npx shadcn-svelte@latest init   # style: default, base color: neutral, CSS variables: yes
npx shadcn-svelte@latest add button input label card table dialog alert-dialog select switch tabs badge sidebar sheet dropdown-menu skeleton separator tooltip sonner checkbox textarea
```

- [ ] **Step 2: Configure SPA output and the dev proxy**

`svelte.config.js`: `adapter-static` with `fallback: 'index.html'`.
`src/routes/+layout.ts`: `export const ssr = false; export const prerender = false;`
`vite.config.ts`: `server.proxy = { '/api': { target: 'http://127.0.0.1:8080', changeOrigin: false } }`. `changeOrigin: false` keeps the `Host` header consistent with the browser origin so the backend's `Origin` check passes.
`.env.example`: `PUBLIC_API_BASE=` (empty means "same origin, use the proxy").

- [ ] **Step 3: Write the failing test for `cn`**

```ts
// src/lib/utils.test.ts
import { describe, expect, it } from 'vitest';
import { cn } from './utils';

describe('cn', () => {
  it('joins truthy classes and drops falsy ones', () => {
    expect(cn('a', false && 'b', undefined, 'c')).toBe('a c');
  });
});
```

- [ ] **Step 4: Run it to verify it fails**

Run: `npm run test -- --run src/lib/utils.test.ts`
Expected: FAIL, cannot resolve `./utils`.

- [ ] **Step 5: Implement `cn`**

`src/lib/utils.ts` exports `cn(...inputs: ClassValue[]): string` using `clsx` + `tailwind-merge` (installed by `shadcn-svelte init`).

- [ ] **Step 6: Verify and commit**

```bash
npm run test -- --run && npm run check && npm run build
git add -A frontend && git commit -m "feat(fe): scaffold sveltekit, tailwind, shadcn-svelte"
```

---

### Task 2: API client with error normalization and CSRF

**Files:**
- Create: `frontend/src/lib/api/errors.ts`, `frontend/src/lib/api/client.ts`, `frontend/src/lib/api/types.ts`
- Test: `frontend/src/lib/api/client.test.ts`, `frontend/src/lib/api/errors.test.ts`

**Interfaces:**
- Consumes: `cn` is unrelated here; nothing else.
- Produces:
  - `class ApiError extends Error { status: number; detail: string; fieldErrors: {key: string; message: string}[]; isMaintenance: boolean; isSetupRequired: boolean }`
  - `setCsrfToken(token: string | null): void`
  - `api<T>(path: string, init?: { method?: 'GET'|'POST'|'PATCH'|'DELETE'; body?: unknown; signal?: AbortSignal }): Promise<T>`
  - `get<T>(path)`, `post<T>(path, body?)`, `patch<T>(path, body?)`, `del<T>(path)`
  - Types mirroring backend payloads: `Device`, `DeviceStatus`, `Role`, `PermissionCategory`, `WebUser`, `TelegramUser`, `Bot`, `BackupRun`, `SettingsSchemaEntry`, `AuditEntry`, `Stats`, `Health`, `AuthMe`, `StreamSnapshot`.

- [ ] **Step 1: Write failing tests**

```ts
// src/lib/api/errors.test.ts
import { describe, expect, it } from 'vitest';
import { ApiError, toApiError } from './errors';

it('reads field errors from the backend 422 shape', async () => {
  const response = new Response(JSON.stringify({ detail: { errors: [{ key: 'name', message: 'wajib' }] } }), { status: 422 });
  const error = await toApiError(response);
  expect(error.status).toBe(422);
  expect(error.fieldErrors).toEqual([{ key: 'name', message: 'wajib' }]);
});

it('flags 409 setup_required and 503 maintenance', async () => {
  const setup = await toApiError(new Response(JSON.stringify({ detail: 'setup_required', setup_required: true }), { status: 409 }));
  expect(setup.isSetupRequired).toBe(true);
  const maint = await toApiError(new Response(JSON.stringify({ detail: 'maintenance', message: 'pemeliharaan' }), { status: 503 }));
  expect(maint.isMaintenance).toBe(true);
  expect(maint.detail).toBe('pemeliharaan');
});
```

```ts
// src/lib/api/client.test.ts
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, setCsrfToken } from './client';
import { ApiError } from './errors';

function mockFetch(response: Response) {
  const spy = vi.fn().mockResolvedValue(response);
  vi.stubGlobal('fetch', spy);
  return spy;
}

afterEach(() => vi.unstubAllGlobals());

it('sends credentials and the csrf header on mutations', async () => {
  const spy = mockFetch(new Response('{}', { status: 200 }));
  setCsrfToken('abc');
  await api('/api/devices', { method: 'POST', body: { name: 'x' } });
  const [, init] = spy.mock.calls[0];
  expect(init.credentials).toBe('same-origin');
  expect(init.headers['X-CSRF-Token']).toBe('abc');
  expect(init.headers['Content-Type']).toBe('application/json');
});

it('omits the csrf header on GET', async () => {
  const spy = mockFetch(new Response('{}', { status: 200 }));
  setCsrfToken('abc');
  await api('/api/devices');
  expect(spy.mock.calls[0][1].headers['X-CSRF-Token']).toBeUndefined();
});

it('turns a network failure into a 0-status ApiError', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
  await expect(api('/api/devices')).rejects.toMatchObject({ status: 0 });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npm run test -- --run src/lib/api`
Expected: FAIL, modules missing.

- [ ] **Step 3: Implement**

`errors.ts` — `toApiError(response: Response): Promise<ApiError>` parses JSON once (falling back to `{}`), maps `detail` string vs `detail.errors`, sets `isSetupRequired` when `status === 409 && body.setup_required`, `isMaintenance` when `status === 503` or `body.detail === 'maintenance'`, and uses `body.message ?? body.detail` for the human text.

`client.ts` — module-level `let csrf: string | null`, set by `setCsrfToken`. `api()` builds `fetch(path, { credentials: 'same-origin', headers, body, signal })`; on `!response.ok` throws `toApiError(response)`; on `fetch` rejection throws `new ApiError(0, 'Tidak dapat terhubung ke backend')`; on 204/empty body returns `undefined as T`.

`types.ts` — hand-written interfaces matching the backend routes (no code generation; OpenAPI is disabled in production and the shapes are small).

- [ ] **Step 4: Verify and commit**

```bash
npm run test -- --run && npm run check
git add -A frontend && git commit -m "feat(fe): api client with csrf and error normalization"
```

---

### Task 3: Auth store, guards, login page, setup wizard

**Files:**
- Create: `frontend/src/lib/stores/auth.svelte.ts`, `frontend/src/lib/stores/theme.svelte.ts`
- Create: `frontend/src/routes/login/+page.svelte`, `frontend/src/routes/setup/+page.svelte`
- Create: `frontend/src/lib/components/theme-toggle.svelte`
- Modify: `frontend/src/routes/+layout.ts`, `frontend/src/routes/+layout.svelte`
- Test: `frontend/src/lib/stores/auth.test.ts`

**Interfaces:**
- Consumes: `api`, `setCsrfToken`, `ApiError` from Task 2.
- Produces:
  - `auth` store: `$state` fields `me: AuthMe | null`, `loading: boolean`, `error: string | null`; methods `hydrate(): Promise<'ready'|'login'|'setup'|'maintenance'>`, `login(username, password)`, `logout()`, `can(permission: string): boolean`, `canAny(...permissions: string[]): boolean`.
  - `theme` store wrapping `mode-watcher` with `current: 'light'|'dark'|'system'`.
  - Route guard in `+layout.ts`: call `auth.hydrate()`; `'login'` → redirect `/login`; `'setup'` → `/setup`; `'maintenance'` → render maintenance screen (no redirect, so a refresh keeps the URL).

- [ ] **Step 1: Write failing tests**

```ts
// src/lib/stores/auth.test.ts
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { auth } from './auth.svelte';
import * as client from '$lib/api/client';

const superadmin = {
  id: 1, username: 'root', actor_kind: 'web',
  role: { id: 1, slug: 'superadmin', name: 'Superadmin' },
  permissions: ['devices.view', 'devices.control', 'users.manage'],
  csrf_token: 'tok-1',
};

beforeEach(() => { auth.reset(); vi.restoreAllMocks(); });

it('hydrate stores me and the csrf token', async () => {
  vi.spyOn(client, 'get').mockResolvedValue(superadmin);
  expect(await auth.hydrate()).toBe('ready');
  expect(auth.me?.username).toBe('root');
  expect(auth.can('devices.control')).toBe(true);
  expect(auth.can('roles.manage')).toBe(false);
});

it('hydrate reports setup and maintenance instead of throwing', async () => {
  const { ApiError } = await import('$lib/api/errors');
  vi.spyOn(client, 'get').mockRejectedValueOnce(new ApiError(409, 'setup_required', [], true, false));
  expect(await auth.hydrate()).toBe('setup');
  vi.spyOn(client, 'get').mockRejectedValueOnce(new ApiError(503, 'maintenance', [], false, true));
  expect(await auth.hydrate()).toBe('maintenance');
  vi.spyOn(client, 'get').mockRejectedValueOnce(new ApiError(401, 'Tidak terautentikasi'));
  expect(await auth.hydrate()).toBe('login');
});

it('a 401 during hydrate clears stale state', async () => {
  vi.spyOn(client, 'get').mockResolvedValueOnce(superadmin);
  await auth.hydrate();
  const { ApiError } = await import('$lib/api/errors');
  vi.spyOn(client, 'get').mockRejectedValueOnce(new ApiError(401, 'Tidak terautentikasi'));
  expect(await auth.hydrate()).toBe('login');
  expect(auth.me).toBeNull();
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npm run test -- --run src/lib/stores`
Expected: FAIL, `auth.svelte` missing.

- [ ] **Step 3: Implement**

`auth.svelte.ts` — runes in a class or plain object with `$state`. `hydrate()` calls `get<AuthMe>('/api/auth/me')`, sets `me`, calls `setCsrfToken(me.csrf_token)`, returns `'ready'`. On `ApiError`, branch on `isSetupRequired` → `'setup'`, `isMaintenance` → `'maintenance'`, `status === 401 || status === 0` → clear and `'login'`; **status 0 (backend down) returns `'offline'` and the layout shows a retry screen** rather than bouncing to login. `login()` posts `/api/auth/login` with `{username, password}`, then calls `setCsrfToken(response.csrf_token)` and `await hydrate()`.

`login/+page.svelte` — card with username/password, submit disabled while pending, field errors from `ApiError.fieldErrors`, toast on success, redirect to `/`.

`setup/+page.svelte` — Indonesian wizard: "Buat akun Superadmin", username + password + confirm, posts `/api/setup`, stores `csrf_token`, calls `hydrate()`, redirects `/`. Shows the one-time notice that setup cannot be repeated.

`theme-toggle.svelte` — three-way control (Terang / Gelap / Sistem) using `mode-watcher`'s `setMode`.

- [ ] **Step 4: Verify and commit**

```bash
npm run test -- --run && npm run check
git add -A frontend && git commit -m "feat(fe): auth store, login and setup wizard"
```

---

### Task 4: App shell, sidebar, permission gating, SSE, maintenance screen

**Files:**
- Create: `frontend/src/lib/components/app-sidebar.svelte`, `frontend/src/lib/components/maintenance-screen.svelte`, `frontend/src/lib/components/offline-screen.svelte`
- Create: `frontend/src/lib/stores/stream.svelte.ts`, `frontend/src/lib/nav.ts`
- Modify: `frontend/src/routes/+layout.svelte`, create `frontend/src/routes/(app)/+layout.svelte`
- Test: `frontend/src/lib/stores/stream.test.ts`, `frontend/src/lib/nav.test.ts`

**Interfaces:**
- Consumes: `auth` from Task 3.
- Produces:
  - `nav.items: {href, label, icon, permission}[]` and `nav.visibleItems(can): typeof nav.items`.
  - `stream` store: `$state devices: Record<string, StreamDevice>`, `connected: boolean`; `start()`, `stop()`; reconnects with exponential backoff (1s → 30s), uses `EventSource('/api/stream')`.
  - Layout renders sidebar (collapsible via shadcn `sidebar`), theme toggle, user menu (logout, "Ubah password"), and a persistent header badge when `stream.connected === false`.

- [ ] **Step 1: Write failing tests**

```ts
// src/lib/nav.test.ts
import { nav } from './nav';

it('hides items whose permission the user lacks', () => {
  const visible = nav.visibleItems((p) => p === 'devices.view');
  expect(visible.map((i) => i.href)).toEqual(['/devices']);
});

it('superadmin sees every page', () => {
  expect(nav.visibleItems(() => true).length).toBe(nav.items.length);
});
```

```ts
// src/lib/stores/stream.test.ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { stream } from './stream.svelte';

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  constructor(public url: string) { FakeEventSource.instances.push(this); }
  close() { this.closed = true; }
}

beforeEach(() => { vi.useFakeTimers(); vi.stubGlobal('EventSource', FakeEventSource); });
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); FakeEventSource.instances = []; stream.reset(); });

it('applies snapshot payloads', () => {
  stream.start();
  const source = FakeEventSource.instances[0];
  source.onmessage?.({ data: JSON.stringify({ devices: [{ id: 1, name: 'pompa', online: true }] }) } as MessageEvent);
  expect(stream.connected).toBe(true);
  expect(stream.devices['pompa'].online).toBe(true);
});

it('reconnects with growing backoff after an error', () => {
  stream.start();
  FakeEventSource.instances[0].onerror?.();
  expect(stream.connected).toBe(false);
  vi.advanceTimersByTime(1000);
  expect(FakeEventSource.instances.length).toBe(2);
  FakeEventSource.instances[1].onerror?.();
  vi.advanceTimersByTime(999);
  expect(FakeEventSource.instances.length).toBe(2);
  vi.advanceTimersByTime(1);
  expect(FakeEventSource.instances.length).toBe(3);
});
```

- [ ] **Step 2: Run to verify failure**

- [ ] **Step 3: Implement**

`nav.ts` — the 12 entries with their permission: Devices (`devices.view`), Log Daya / Aktivitas / Error (`logs.view`), Settings (`settings.view`), Users (`users.view`), Telegram Users (`telegram_users.view`), Roles (`users.view`), Bots (`bots.view`), Backup (`backup.view`), System (`system.view`).

`stream.svelte.ts` — `EventSource` with `withCredentials` semantics automatic for same-origin; store snapshot map keyed by device `name`; on `error` close, set `connected=false`, schedule reconnect with `Math.min(30000, 1000 * 2**attempt)`.

`(app)/+layout.svelte` — requires `auth.me`, starts/stops `stream` on mount/unmount, renders sidebar + `<slot/>`.

`maintenance-screen.svelte` — full-page message with retry button calling `auth.hydrate()`; `offline-screen.svelte` — "Backend tidak dapat dihubungi" with the attempted URL and retry.

- [ ] **Step 4: Verify and commit**

```bash
npm run test -- --run && npm run check
git add -A frontend && git commit -m "feat(fe): app shell, sidebar, sse store"
```

---

### Task 5: Devices list, detail, control, scan

**Files:**
- Create: `frontend/src/routes/(app)/devices/+page.svelte`, `frontend/src/routes/(app)/devices/[id]/+page.svelte`
- Create: `frontend/src/lib/components/device-card.svelte`, `frontend/src/lib/components/device-dialog.svelte`, `frontend/src/lib/components/scan-dialog.svelte`, `frontend/src/lib/components/dps-editor.svelte`
- Create: `frontend/src/lib/format.ts`
- Test: `frontend/src/lib/format.test.ts`, `frontend/src/routes/(app)/devices/devices.test.ts`

**Interfaces:**
- Consumes: `api`, `stream`, `auth`, `nav`.
- Produces: `format.watts(value)`, `format.volts(value)`, `format.amps(value)`, `format.age(seconds)`, `format.bytes(n)` used by logs and system pages too.

- [ ] **Step 1: Write failing tests**

```ts
// src/lib/format.test.ts
import { format } from './format';

it('formats power readings with one decimal and a unit', () => {
  expect(format.watts(12.34)).toBe('12.3 W');
  expect(format.watts(null)).toBe('--');
});

it('formats data ages in Indonesian', () => {
  expect(format.age(5)).toBe('5 detik lalu');
  expect(format.age(120)).toBe('2 menit lalu');
  expect(format.age(null)).toBe('belum ada data');
});
```

```ts
// devices.test.ts — tests the query helpers, not the DOM
import { deviceErrorText } from './devices-page';
it('explains an unreachable device instead of showing a raw error', () => {
  expect(deviceErrorText({ success: false, message: 'Timeout 25s saat menghubungi perangkat' }))
    .toBe('Perangkat tidak merespons. Periksa IP dan local key.');
});
```

- [ ] **Step 2: Run to verify failure**

- [ ] **Step 3: Implement**

`devices/+page.svelte` — grid of `device-card` fed by `stream.devices`, falling back to `GET /api/devices` on load; each card shows label, online dot, switch state, power if mapped, and an on/off button disabled unless `auth.can('devices.control')` **and** the device is visible to the role. Confirmation dialog for devices with `features.watchdog`. Header actions: "Tambah device" (`devices.manage`), "Scan LAN" (`devices.scan`).

`device-dialog.svelte` — create/edit form; `dps-editor` prefilled from `GET /api/devices/templates`; `access_roles` multi-select of roles; `features` checkboxes; validates client-side only for required fields, trusting server 422 `fieldErrors` for the rest.

`scan-dialog.svelte` — `POST /api/devices/scan`, then poll `GET /api/devices/scan/{job_id}` every 1.5 s until `status !== 'running'`; results table with "Gunakan" that prefills `device-dialog`.

`devices/[id]/+page.svelte` — detail with raw DPS table from `GET /api/devices/{id}/status`, "Test koneksi" calling `/test`, and the same edit/delete actions.

- [ ] **Step 4: Verify and commit**

```bash
npm run test -- --run && npm run check
git add -A frontend && git commit -m "feat(fe): devices list, detail, control and scan"
```

---

### Task 6: Log pages

**Files:**
- Create: `frontend/src/routes/(app)/logs/power/+page.svelte`, `.../logs/activities/+page.svelte`, `.../logs/errors/+page.svelte`
- Create: `frontend/src/lib/components/log-table.svelte`, `frontend/src/lib/components/device-filter.svelte`
- Test: `frontend/src/lib/components/log-table.test.ts`

**Interfaces:**
- Consumes: `api`, `format`, `stream`.
- Produces: `logTable.rows<T>(fetcher, {limit, offset, deviceId})` — returns `{items, loading, error, next, prev}`; shared by all three pages.

- [ ] **Step 1: Write failing test**

```ts
it('paginates with a fixed page size of 50 and stops at an empty page', async () => {
  const calls: string[] = [];
  const fetcher = async (path: string) => { calls.push(path); return { items: path.includes('offset=50') ? [] : [{ id: 1 }] }; };
  const table = logTable.rows<{ id: number }>(fetcher, { limit: 50 });
  await table.load();
  expect(table.items.length).toBe(1);
  await table.next();
  expect(calls[1]).toContain('offset=50');
  expect(table.hasNext).toBe(false);
});
```

- [ ] **Step 2: Run to verify failure**

- [ ] **Step 3: Implement**

Each page uses `log-table` with its own columns: power (`created_at`, device, W/V/A, switch, source), activities (`created_at`, device, actor, action, status, message), errors (`created_at`, level, logger, message, expandable trace). Device filter pulls from `/api/devices`. Empty states in Indonesian. `logs/power` additionally renders a simple 24-hour sparkline from the loaded rows using inline SVG (no chart library).

- [ ] **Step 4: Verify and commit**

```bash
npm run test -- --run && npm run check
git add -A frontend && git commit -m "feat(fe): power, activity and error log pages"
```

---

### Task 7: Settings page driven by the schema

**Files:**
- Create: `frontend/src/routes/(app)/settings/+page.svelte`
- Create: `frontend/src/lib/components/setting-field.svelte`, `frontend/src/lib/settings-form.ts`
- Test: `frontend/src/lib/settings-form.test.ts`

**Interfaces:**
- Consumes: `api`, `auth`.
- Produces: `settingsForm.fromSchema(schema, values)` → `{ groups, dirty, changed, toPayload(), validate() }`.

- [ ] **Step 1: Write failing tests**

```ts
it('groups settings by category and keeps them in registry order', () => {
  const form = settingsForm.fromSchema(
    [
      { key: 'a.x', category: 'Alpha', type: 'int', default: 1, minimum: 0, maximum: 10, read_only: false },
      { key: 'b.y', category: 'Beta', type: 'bool', default: true, read_only: false },
      { key: 'a.z', category: 'Alpha', type: 'string', default: 'q', read_only: false },
    ],
    {},
  );
  expect(form.groups.map((g) => g.name)).toEqual(['Alpha', 'Beta']);
  expect(form.groups[0].fields.map((f) => f.key)).toEqual(['a.x', 'a.z']);
});

it('sends only changed values and never sends read-only keys', () => {
  const form = settingsForm.fromSchema(
    [
      { key: 'a.x', category: 'A', type: 'int', default: 1, read_only: false },
      { key: 'sys.v', category: 'S', type: 'int', default: 9, read_only: true },
    ],
    { 'a.x': 5, 'sys.v': 9 },
  );
  form.set('a.x', 7);
  form.set('sys.v', 10);
  expect(form.toPayload()).toEqual({ 'a.x': 7 });
});

it('flags a value outside the declared range before sending', () => {
  const form = settingsForm.fromSchema(
    [{ key: 'a.x', category: 'A', type: 'int', default: 1, minimum: 1, maximum: 10, read_only: false }],
    { 'a.x': 1 },
  );
  form.set('a.x', 11);
  expect(form.validate()).toEqual([{ key: 'a.x', message: 'Maksimal 10' }]);
});
```

- [ ] **Step 2: Run to verify failure**

- [ ] **Step 3: Implement**

`setting-field.svelte` renders by type: `bool` → switch, `int`/`float` → number input with min/max, `enum` → select, `string` → input, `secret` → password input showing "sudah diisi" when `{has_value: true}` and never the value, `json` → textarea with JSON validation. Each field shows its `apply` badge: `live` → "langsung", `telegram_restart` → "restart bot".

Page: fetch `GET /api/settings`, render groups, sticky save bar showing count of changes, PATCH `{values}`, map 422 field errors back onto fields, toast on success. Read-only `system.*` fields render disabled with a "khusus sistem" hint.

- [ ] **Step 4: Verify and commit**

```bash
npm run test -- --run && npm run check
git add -A frontend && git commit -m "feat(fe): schema-driven settings page"
```

---

### Task 8: Users, Telegram users, roles, bots

**Files:**
- Create: `frontend/src/routes/(app)/users/+page.svelte`, `.../telegram-users/+page.svelte`, `.../roles/+page.svelte`, `.../roles/[id]/+page.svelte`, `.../bots/+page.svelte`
- Create: `frontend/src/lib/components/permission-matrix.svelte`, `frontend/src/lib/components/role-dialog.svelte`, `frontend/src/lib/components/bot-dialog.svelte`
- Test: `frontend/src/lib/permissions.test.ts`

**Interfaces:**
- Consumes: `api`, `auth`.
- Produces: `permissions.groupCatalog(payload)` → `{name, permissions: {key, label}[]}[]` with Indonesian labels; `permissions.editable(catalog, actorPermissions)` → the subset the actor may grant.

- [ ] **Step 1: Write failing tests**

```ts
it('labels every catalog key in Indonesian', () => {
  const grouped = permissions.groupCatalog(catalogPayload);
  const flat = grouped.flatMap((g) => g.permissions);
  expect(flat.length).toBe(catalogPayload.all.length);
  expect(flat.every((p) => p.label.length > 0)).toBe(true);
  expect(flat.find((p) => p.key === 'devices.control')?.label).toBe('Kontrol perangkat');
});

it('only offers permissions the actor already holds', () => {
  const editable = permissions.editable(catalogPayload, ['devices.view', 'devices.control']);
  expect(editable).toEqual(['devices.view', 'devices.control']);
});
```

- [ ] **Step 2: Run to verify failure**

- [ ] **Step 3: Implement**

`users/+page.svelte` — table (username, role, aktif, login terakhir), create/edit dialog with password reset, deactivate toggle, delete. Deactivating the last `users.manage` holder returns 409 and is shown as a field-level explanation, not a generic toast.

`telegram-users/+page.svelte` — table (`telegram_id`, label, role, aktif), add form taking a numeric ID, role select limited to `permissions.editable`, delete.

`roles/+page.svelte` — cards with permission count and user count; `[id]` editor uses `permission-matrix` (grouped checkboxes with "pilih semua" per group, protected keys disabled with a lock icon and tooltip "izin inti role terlindungi"). Shows the warning that changing permissions revokes sessions of affected users.

`bots/+page.svelte` — cards with label, `@username`, runtime status badge, last error (monospace, truncated), enable/disable switch, "Uji" button, "Ganti token" dialog (write-only input, confirms it cannot be read back), delete with confirmation.

- [ ] **Step 4: Verify and commit**

```bash
npm run test -- --run && npm run check
git add -A frontend && git commit -m "feat(fe): users, telegram users, roles and bots"
```

---

### Task 9: Backup, system, Docker/nginx, CI, docs

**Files:**
- Create: `frontend/src/routes/(app)/backup/+page.svelte`, `.../system/+page.svelte`
- Create: `frontend/src/lib/components/restore-dialog.svelte`, `frontend/src/lib/components/audit-table.svelte`
- Create: `frontend/Dockerfile`, `frontend/nginx.conf`, `frontend/.dockerignore`
- Create: `.github/workflows/frontend.yml`
- Create: `frontend/README.md`
- Modify: root `docker-compose.yml` (add the frontend service), root `README.md`
- Test: `frontend/src/lib/backup.test.ts`

**Interfaces:**
- Consumes: everything.
- Produces: `docker compose up` serving the dashboard on port 80 with `/api` proxied to the backend container.

- [ ] **Step 1: Write failing test**

```ts
it('requires the typed confirmation and current password before restore', () => {
  const form = backupForm.restore();
  form.setPassword('rahasia');
  form.setConfirm('bukan');
  expect(form.valid).toBe(false);
  form.setConfirm('RESTORE');
  expect(form.valid).toBe(true);
});
```

- [ ] **Step 2: Run to verify failure**

- [ ] **Step 3: Implement pages**

`backup/+page.svelte` — table of runs (filename, kind badge, size, created_at), "Buat backup" (`backup.create`), download button (`backup.restore` permission, warning label "berisi seluruh data termasuk rahasia"), restore dialog with password + typed `RESTORE` and a warning that the app switches to maintenance. Restore upload uses `FormData` to `POST /api/backup/restore`; on 422 with `stage` show the stage name in Indonesian.

`system/+page.svelte` — health cards (status, database, devices fresh/total, maintenance), stats block (DB path/size/schema version, row counts, last backup), maintenance toggle with reason + auto-off minutes, and `audit-table` with filters (actor kind, action, result, date range) and a details drawer showing JSON.

- [ ] **Step 4: Implement deployment**

`nginx.conf` — `location /api/ { proxy_pass http://backend:8080; proxy_set_header Host $host; proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; }`, `proxy_buffering off` for `/api/stream`, `location / { try_files $uri /index.html; }`, `add_header Cache-Control "no-store"` for `/index.html`.
`Dockerfile` — `node:24-alpine` build stage (`npm ci && npm run build`), `nginx:alpine` runtime copying `build/` and the config.
Root `docker-compose.yml` — add `frontend` service publishing `80:80`, `depends_on: backend`, no `network_mode: host` (it talks to the backend by service name).
`.github/workflows/frontend.yml` — `npm ci`, `npm run check`, `npm run test -- --run`, `npm run build`, with `working-directory: frontend`.

- [ ] **Step 5: Verify**

```bash
cd frontend
npm run test -- --run && npm run check && npm run build
cd ..
git add -A && git commit -m "feat(fe): backup and system pages, container, ci"
```

- [ ] **Step 6: End-to-end smoke (backend must run)**

```bash
# terminal 1
cd backend && PYTHONPATH=src python -m tuyabot.main
# terminal 2
cd frontend && npm run dev
```

Expected: `/setup` completes, login succeeds, devices page shows the SSE badge "terhubung", a device can be created and toggled, settings save, backup creates a row, system shows health `ok|degraded`.

---

## Self-Review Notes

- Spec §8.16 (Frontend) maps to: layout/theme (T1, T4), auth guard and CSRF (T2, T3), settings from schema (T7), roles with checkboxes and protected keys (T8), two separate user pages (T8), bots token write-only (T8), backup double confirmation (T9), accessibility and responsive layout (T4, T5).
- Spec §8.15 API list is fully covered by the types in T2 and the pages in T5–T9. `GET /api/health` and `GET /api/maintenance/status` are used by T4 and T9.
- Deliberately out of scope: charts library, CSV export, i18n framework, offline/PWA, Playwright E2E (the backend requirement makes a unit-level gate sufficient for now; the smoke step at T9 is manual).

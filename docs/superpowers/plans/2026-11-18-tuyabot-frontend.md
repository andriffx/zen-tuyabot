# Zen Tuyabot Frontend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the dashboard SPA that drives the existing Zen Tuyabot backend: setup wizard, login, overview, devices, logs, settings, users, roles, bots, backup, and system pages behind a sidebar shell.

**Architecture:** SvelteKit with SSR disabled (pure SPA, `adapter-static` + `index.html` fallback). One `api/` client owns every HTTP concern — cookie credentials, CSRF header, error normalization, JSON and binary/FormData bodies. Auth and permission state live in a runes store hydrated from `GET /api/auth/me`; the guard maps outcomes to `/login`, `/setup`, a maintenance screen, or an offline screen. Vite proxies `/api` to the backend in dev; nginx proxies it in production, so cookies stay same-origin.

**Tech Stack:** SvelteKit 3.x, Svelte 5 (runes), TypeScript, Tailwind CSS 4, shadcn-svelte 1.x, mode-watcher (theme), svelte-sonner (toasts), Vitest + @testing-library/svelte, svelte-check.

**Spec:** `docs/superpowers/specs/2026-11-17-tuyabot-rebuild-design.md` (§7.2, §8.15, §8.16)

## Global Constraints

- Monorepo root is `zen-tuyabot/`; this plan writes only inside `frontend/`.
- The backend is required. No mock server, no MSW. If `/api` is unreachable the UI shows an offline screen with retry — never fake data.
- Node 24, npm 11. No pnpm, no yarn.
- Svelte 5 runes only (`$state`, `$derived`, `$effect`). No `export let`, no `svelte/store` for new code.
- UI copy is Indonesian with English technical terms kept as-is: "Settings", "Backup", "Role", "Permission", "Device", "Bot", "Restore", "Maintenance", "Audit log", "Scan", "DPS". Never translate API field names.
- Every mutating request (POST/PATCH/DELETE) sends `X-CSRF-Token` from the auth store. GET never sends it.
- Never store credentials or the session token in `localStorage`. The session is an `HttpOnly` cookie; the CSRF token lives in memory only.
- All API failures surface as `ApiError { status, detail, fieldErrors, isSetupRequired, isMaintenance, isOffline }`. Never render raw backend text as HTML.
- `npm run check` (svelte-check) and `npm run test` pass at the end of every task.
- Backend payloads are read from the backend source in this repo, not guessed. Where a shape matters it is copied into this plan.

### Verified backend contract (read from `backend/src/tuyabot/web/routes/`)

```
GET  /api/setup/status            -> { required: bool, steps_done: { admin: bool } }
POST /api/setup                   -> { authenticated, user_id, csrf_token }   (sets cookies)
GET  /api/auth/csrf               -> { csrf_token }                            (public)
POST /api/auth/login              -> { authenticated, user_id, csrf_token }   (sets cookies)
POST /api/auth/logout             -> { authenticated: false }
GET  /api/auth/me                 -> { id, username, actor_kind, role: {id,slug,name}|null,
                                       permissions: string[], csrf_token: string|null }
POST /api/auth/password           -> { changed, sessions_revoked }
GET  /api/auth/sessions           -> { sessions: [...] }
DELETE /api/auth/sessions/{id}    -> { revoked: bool }

GET  /api/devices                 -> { devices: Device[] }
GET  /api/devices/templates       -> { templates: Record<type, Record<semantic,int>>, types, features }
POST /api/devices                 -> Device
PATCH/DELETE /api/devices/{id}    -> Device | { deleted: true }
POST /api/devices/{id}/on|off     -> { success, message, device_id, state }
GET  /api/devices/{id}/status     -> { id, name, success, online, switch_on?, power_w?,
                                       current_a?, voltage_v?, age_seconds?, message? }
POST /api/devices/{id}/test       -> { success, raw?, mapped?, dps? } | { success:false, message }
POST /api/devices/scan            -> { job_id, status: "running" }
GET  /api/devices/scan/{job_id}   -> { job_id, status: "running"|"done"|"error",
                                       candidates: [{ip, tuya_id, version, product_key, name}], error }

GET  /api/logs/activities|power|errors?limit&offset&device_id -> { items: [...] }
GET  /api/settings                -> { values: Record<string, unknown>, schema: SettingsSchemaEntry[] }
PATCH /api/settings               -> { changed, values, schema } | 422 detail.errors[]
GET  /api/roles                   -> { roles: Role[] }
GET  /api/roles/permissions       -> { categories: [{name, permissions: string[]}], all: string[] }
POST/PATCH/DELETE /api/roles[/{id}]-> Role | { deleted: true }
GET  /api/web-users               -> { users: WebUser[] }
GET  /api/telegram-users          -> { telegram_users: TelegramUser[] }
GET  /api/bots                    -> { bots: Bot[] }
GET  /api/backup                  -> { backups: BackupRun[] }
POST /api/backup                  -> { id, filename, path, size_bytes }
GET  /api/backup/{id}/download    -> binary (application/octet-stream)
POST /api/backup/restore          -> { restored, from_version, schema_version, pre_restore_backup }
                                     (multipart: file, password, confirm)
GET  /api/stats                   -> { devices:{total,online,offline}, rows:{...},
                                       database:{path,size_bytes,schema_version},
                                       backup:{last,last_at}, process:{pid} }
GET  /api/health                  -> { status: "ok"|"degraded"|"down", database, devices_total,
                                       devices_fresh, maintenance }
GET  /api/audit                   -> { items, limit, offset }
GET  /api/maintenance/status      -> { maintenance: bool }
GET  /api/maintenance             -> { maintenance, state }
POST /api/maintenance             -> { maintenance, state }
GET  /api/stream                  -> SSE: { ts, devices: [{ id, name, label, online, switch_on,
                                       power_w, voltage_v, current_a, age_seconds }] }
```

Device object (from `GET /api/devices`):
`{ id, name, label, type, ip, version, dps, features, access_roles, is_active, sort_order, last_seen_at, last_error, has_local_key }`.
`local_key` and `tuya_id` are never returned.

## Review Focus

Failure modes the spec implies; each is pinned by a test in the named task.

1. **Backend down or restarting** — every page shows the offline screen with retry; no empty "successful" screen. (Task 3)
2. **Session expires mid-use** — the next request returns 401; auth state clears and the app lands on `/login` exactly once, with no redirect loop. (Task 4)
3. **CSRF token lost on reload** — a hard refresh clears in-memory state; the first mutation must not fail 403 because hydrate runs before any action. (Task 4)
4. **Maintenance mode on** — non-auth routes return 503 `detail: "maintenance"`; the app shows the maintenance screen, not an error toast per page. (Task 4)
5. **Permission revoked while logged in** — role edits revoke sessions server-side; a stale UI must not keep offering actions the user can no longer perform. (Task 5)

---

## Milestones

| # | Milestone | Tasks |
|---|---|---|
| 1 | Foundation | Task 1 |
| 2 | API client + types | Task 2 |
| 3 | Authentication | Task 3 |
| 4 | Application shell | Task 4 |
| 5 | Device management | Task 5 |
| 6 | Dashboard overview | Task 6 |
| 7 | Management pages | Task 7 |
| 8 | Monitoring | Task 8 |
| 9 | Backup, container, CI | Task 9 |

---

### Task 1: Scaffold SvelteKit, Tailwind 4, shadcn-svelte, dev proxy

**Files:**
- Create: `frontend/package.json`, `frontend/svelte.config.js`, `frontend/vite.config.ts`, `frontend/tsconfig.json`
- Create: `frontend/src/app.html`, `frontend/src/app.css`, `frontend/src/routes/+layout.ts`, `frontend/src/routes/+layout.svelte`, `frontend/src/routes/+page.svelte`
- Create: `frontend/components.json`, `frontend/vitest.config.ts`, `frontend/src/lib/utils.ts`, `frontend/vitest-setup.ts`
- Create: `frontend/.env.example`
- Test: `frontend/src/lib/utils.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces: dev server on 5173 with `/api` reaching 8080; `cn(...classes)`; scripts `dev`, `build`, `check`, `test`.

- [ ] **Step 1: Create the project and install**

```bash
cd "D:/Datas/MyData/Project Repo/zen-tuyabot"
npx sv create frontend --template minimal --types ts --no-add-ons --install npm
cd frontend
npm i -D @sveltejs/adapter-static tailwindcss @tailwindcss/vite vitest jsdom \
      @testing-library/svelte @testing-library/jest-dom svelte-check
npm i mode-watcher svelte-sonner
npx shadcn-svelte@latest init      # style: default, base color: neutral, CSS variables: yes
npx shadcn-svelte@latest add button input label card table dialog alert-dialog select \
      switch tabs badge sidebar sheet dropdown-menu skeleton separator tooltip sonner \
      checkbox textarea progress
```

- [ ] **Step 2: Configure SPA output, proxy, and vitest**

`svelte.config.js`: `adapter-static` with `fallback: 'index.html'`.
`src/routes/+layout.ts`: `export const ssr = false; export const prerender = false;`
`vite.config.ts`:
- `server.proxy['/api'] = { target: 'http://127.0.0.1:8080', changeOrigin: false }` — `changeOrigin:false` keeps `Host` equal to the browser origin so the backend's `Origin` check passes.
- `test` block: `environment: 'jsdom'`, `setupFiles: ['./vitest-setup.ts']`, `include: ['src/**/*.test.ts']`.
`vitest-setup.ts`: imports `@testing-library/jest-dom/vitest`.
`app.css`: `@import 'tailwindcss';` plus the shadcn theme variables already generated.
`.env.example`: `PUBLIC_API_BASE=` with a comment that empty means same-origin via proxy.

- [ ] **Step 3: Write the failing test**

```ts
// src/lib/utils.test.ts
import { describe, expect, it } from 'vitest';
import { cn } from './utils';

describe('cn', () => {
  it('joins truthy classes and drops falsy ones', () => {
    expect(cn('a', false && 'b', undefined, 'c')).toBe('a c');
  });

  it('lets a later tailwind class win', () => {
    expect(cn('p-2', 'p-4')).toBe('p-4');
  });
});
```

- [ ] **Step 4: Run it to verify it fails**

Run: `npm run test -- --run src/lib/utils.test.ts`
Expected: FAIL, cannot resolve `./utils`.

- [ ] **Step 5: Implement `cn`**

`src/lib/utils.ts` exports `cn(...inputs: ClassValue[]): string` using `clsx` + `tailwind-merge`.

- [ ] **Step 6: Verify and commit**

```bash
npm run test -- --run && npm run check && npm run build
git add -A frontend && git commit -m "feat(fe): scaffold sveltekit, tailwind, shadcn-svelte"
```

---

### Task 2: API client, error model, types

**Files:**
- Create: `frontend/src/lib/api/errors.ts`, `frontend/src/lib/api/client.ts`, `frontend/src/lib/api/types.ts`, `frontend/src/lib/api/index.ts`
- Test: `frontend/src/lib/api/client.test.ts`, `frontend/src/lib/api/errors.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `type FieldError = { key: string; message: string }`
  - `class ApiError extends Error { status: number; detail: string; fieldErrors: FieldError[]; isSetupRequired: boolean; isMaintenance: boolean; isOffline: boolean }`
  - `setCsrfToken(token: string | null): void`
  - `api<T>(path, init?: ApiInit): Promise<T>` where `ApiInit = { method?: HttpMethod; body?: unknown; form?: FormData; signal?: AbortSignal }`
  - `get<T>`, `post<T>`, `patch<T>`, `del<T>`
  - `download(path: string, filename: string): Promise<void>` — streams a binary response to disk via `Blob` + object URL.
  - Types: `AuthMe`, `SetupStatus`, `Device`, `DeviceStatus`, `DeviceTemplates`, `ScanJob`, `ScanCandidate`, `LogItems<T>`, `SettingsSchemaEntry`, `Role`, `PermissionCategory`, `WebUser`, `TelegramUser`, `Bot`, `BackupRun`, `Stats`, `Health`, `AuditEntry`, `StreamDevice`, `StreamSnapshot`, `RestoreResult`.

- [ ] **Step 1: Write failing tests**

```ts
// src/lib/api/errors.test.ts
import { describe, expect, it } from 'vitest';
import { toApiError } from './errors';

it('reads field errors from the backend 422 shape', async () => {
  const response = new Response(
    JSON.stringify({ detail: { errors: [{ key: 'name', message: 'wajib' }] } }),
    { status: 422, headers: { 'content-type': 'application/json' } },
  );
  const error = await toApiError(response);
  expect(error.status).toBe(422);
  expect(error.fieldErrors).toEqual([{ key: 'name', message: 'wajib' }]);
});

it('treats a non-JSON body as a plain message, never as HTML', async () => {
  const response = new Response('<html>502 Bad Gateway</html>', { status: 502 });
  const error = await toApiError(response);
  expect(error.status).toBe(502);
  expect(error.detail).toBe('Bad Gateway');       // statusText, not the HTML body
  expect(error.fieldErrors).toEqual([]);
});

it('flags setup_required, maintenance and offline', async () => {
  const setup = await toApiError(new Response(JSON.stringify({ detail: 'setup_required', setup_required: true }), { status: 409 }));
  expect(setup.isSetupRequired).toBe(true);

  const maintenance = await toApiError(new Response(JSON.stringify({ detail: 'maintenance', message: 'pemeliharaan' }), { status: 503 }));
  expect(maintenance.isMaintenance).toBe(true);
  expect(maintenance.detail).toBe('pemeliharaan');

  const offline = toApiError.offline();
  expect(offline.isOffline).toBe(true);
  expect(offline.status).toBe(0);
});
```

```ts
// src/lib/api/client.test.ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api, download, setCsrfToken } from './client';

function mockFetch(response: Response) {
  const spy = vi.fn().mockResolvedValue(response);
  vi.stubGlobal('fetch', spy);
  return spy;
}

beforeEach(() => setCsrfToken(null));
afterEach(() => vi.unstubAllGlobals());

it('sends credentials and the csrf header on mutations', async () => {
  const spy = mockFetch(new Response('{}', { status: 200 }));
  setCsrfToken('abc');
  await api('/api/devices', { method: 'POST', body: { name: 'x' } });
  const [url, init] = spy.mock.calls[0];
  expect(url).toBe('/api/devices');
  expect(init.credentials).toBe('same-origin');
  expect(init.headers['X-CSRF-Token']).toBe('abc');
  expect(init.headers['Content-Type']).toBe('application/json');
  expect(init.body).toBe('{"name":"x"}');
});

it('omits the csrf header on GET', async () => {
  const spy = mockFetch(new Response('{}', { status: 200 }));
  setCsrfToken('abc');
  await api('/api/devices');
  expect(spy.mock.calls[0][1].headers['X-CSRF-Token']).toBeUndefined();
});

it('does not set Content-Type for FormData so the browser adds the boundary', async () => {
  const spy = mockFetch(new Response('{}', { status: 200 }));
  setCsrfToken('abc');
  const form = new FormData();
  form.set('confirm', 'RESTORE');
  await api('/api/backup/restore', { method: 'POST', form });
  const init = spy.mock.calls[0][1];
  expect(init.body).toBe(form);
  expect(init.headers['Content-Type']).toBeUndefined();
  expect(init.headers['X-CSRF-Token']).toBe('abc');
});

it('returns undefined for 204 and empty bodies', async () => {
  mockFetch(new Response(null, { status: 204 }));
  await expect(api('/api/x', { method: 'DELETE' })).resolves.toBeUndefined();
});

it('turns a network failure into an offline ApiError', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
  await expect(api('/api/devices')).rejects.toMatchObject({ isOffline: true, status: 0 });
});

it('downloads a binary response through a blob url', async () => {
  const spy = mockFetch(new Response(new Blob(['data']), {
    status: 200, headers: { 'content-disposition': 'attachment; filename="a.db"' },
  }));
  const createObjectURL = vi.fn().mockReturnValue('blob:x');
  const revokeObjectURL = vi.fn();
  vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL });
  const click = vi.fn();
  vi.spyOn(document, 'createElement').mockReturnValue({ click, set href(v) {}, download: '' } as never);

  await download('/api/backup/1/download', 'a.db');
  expect(spy.mock.calls[0][1].credentials).toBe('same-origin');
  expect(createObjectURL).toHaveBeenCalled();
  expect(revokeObjectURL).toHaveBeenCalledWith('blob:x');
  expect(click).toHaveBeenCalled();
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npm run test -- --run src/lib/api`
Expected: FAIL, modules missing.

- [ ] **Step 3: Implement**

`errors.ts`:
- Parse JSON only when `content-type` includes `application/json`; otherwise use `response.statusText || 'Terjadi kesalahan'`. This is what keeps an nginx HTML error page from reaching the UI as markup.
- `isSetupRequired` when `status === 409 && body.setup_required === true`.
- `isMaintenance` when `status === 503` **or** `body.detail === 'maintenance'`.
- `detail` = `body.message ?? body.detail ?? statusText`.
- `toApiError.offline()` returns status 0 with `isOffline`.

`client.ts`:
- Module-level `csrf: string | null`.
- `api()`: build headers `{ Accept: 'application/json' }`; add `Content-Type: application/json` only for a JSON `body`; add `X-CSRF-Token` only for mutations when `csrf` is set; never add `Content-Type` when `form` is present.
- On `!response.ok` throw `toApiError(response)`. On a thrown `TypeError` from fetch, throw `toApiError.offline()`.
- Empty body → `undefined`.
- `download()` uses raw `fetch` with `credentials`, throws `toApiError` on failure, then Blob → object URL → anchor click → `revokeObjectURL`.

`types.ts`: every type above, transcribed from the verified contract in the header. No `any`.

- [ ] **Step 4: Verify and commit**

```bash
npm run test -- --run && npm run check
git add -A frontend && git commit -m "feat(fe): api client, binary download, error model, types"
```

---

### Task 3: Auth store, login, setup wizard, theme

**Files:**
- Create: `frontend/src/lib/stores/auth.svelte.ts`, `frontend/src/lib/stores/theme.svelte.ts`
- Create: `frontend/src/routes/login/+page.svelte`, `frontend/src/routes/setup/+page.svelte`
- Create: `frontend/src/lib/components/theme-toggle.svelte`, `frontend/src/lib/components/offline-screen.svelte`
- Create: `frontend/src/lib/guard.ts`
- Modify: `frontend/src/routes/+layout.svelte`
- Test: `frontend/src/lib/stores/auth.test.ts`, `frontend/src/lib/guard.test.ts`

**Interfaces:**
- Consumes: `api`, `setCsrfToken`, `ApiError` (Task 2).
- Produces:
  - `type HydrateOutcome = 'ready' | 'login' | 'setup' | 'maintenance' | 'offline'`
  - `auth`: `$state me: AuthMe | null`, `loading: boolean`, `error: string | null`;
    `hydrate(): Promise<HydrateOutcome>`; `login(u: string, p: string): Promise<void>`;
    `logout(): Promise<void>`; `can(permission: string): boolean`;
    `canAny(...permissions: string[]): boolean`; `reset(): void`.
  - `guard.outcomeToLocation(outcome: HydrateOutcome, pathname: string): { redirect?: string; render?: 'offline'|'maintenance' }`.

- [ ] **Step 1: Write failing tests**

```ts
// src/lib/guard.test.ts
import { describe, expect, it } from 'vitest';
import { outcomeToLocation } from './guard';

it('sends anonymous users to login except on the public pages', () => {
  expect(outcomeToLocation('login', '/devices')).toEqual({ redirect: '/login' });
  expect(outcomeToLocation('login', '/login')).toEqual({});
});

it('sends everyone to setup until setup is complete', () => {
  expect(outcomeToLocation('setup', '/login')).toEqual({ redirect: '/setup' });
  expect(outcomeToLocation('setup', '/setup')).toEqual({});
});

it('renders screens instead of redirecting for maintenance and offline', () => {
  expect(outcomeToLocation('maintenance', '/devices')).toEqual({ render: 'maintenance' });
  expect(outcomeToLocation('offline', '/devices')).toEqual({ render: 'offline' });
  expect(outcomeToLocation('offline', '/setup')).toEqual({ render: 'offline' });
});
```

```ts
// src/lib/stores/auth.test.ts
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { auth } from './auth.svelte';
import * as client from '$lib/api/client';
import { toApiError } from '$lib/api/errors';

const me = {
  id: 1, username: 'root', actor_kind: 'web',
  role: { id: 1, slug: 'superadmin', name: 'Superadmin' },
  permissions: ['devices.view', 'devices.control', 'users.manage'],
  csrf_token: 'tok-1',
};

beforeEach(() => { auth.reset(); vi.restoreAllMocks(); });

it('hydrate stores me, csrf and permissions', async () => {
  vi.spyOn(client, 'get').mockResolvedValue(me);
  expect(await auth.hydrate()).toBe('ready');
  expect(auth.can('devices.control')).toBe(true);
  expect(auth.can('roles.manage')).toBe(false);
  expect(auth.canAny('roles.manage', 'devices.view')).toBe(true);
});

it('maps each failure to its outcome', async () => {
  const get = vi.spyOn(client, 'get');
  get.mockRejectedValueOnce(await toApiError(new Response(JSON.stringify({ setup_required: true }), { status: 409 })));
  expect(await auth.hydrate()).toBe('setup');
  get.mockRejectedValueOnce(await toApiError(new Response(JSON.stringify({ detail: 'maintenance' }), { status: 503 })));
  expect(await auth.hydrate()).toBe('maintenance');
  get.mockRejectedValueOnce(await toApiError(new Response('{}', { status: 401 })));
  expect(await auth.hydrate()).toBe('login');
  get.mockRejectedValueOnce(toApiError.offline());
  expect(await auth.hydrate()).toBe('offline');
});

it('a 401 clears stale state so the UI cannot keep showing admin screens', async () => {
  vi.spyOn(client, 'get').mockResolvedValueOnce(me);
  await auth.hydrate();
  vi.spyOn(client, 'get').mockRejectedValueOnce(await toApiError(new Response('{}', { status: 401 })));
  await auth.hydrate();
  expect(auth.me).toBeNull();
  expect(auth.can('devices.control')).toBe(false);
});

it('login refreshes the csrf token before hydrating', async () => {
  const setCsrf = vi.spyOn(client, 'setCsrfToken');
  vi.spyOn(client, 'post').mockResolvedValue({ authenticated: true, user_id: 1, csrf_token: 'tok-2' });
  vi.spyOn(client, 'get').mockResolvedValue({ ...me, csrf_token: 'tok-2' });
  await auth.login('root', 'password-panjang');
  expect(setCsrf).toHaveBeenCalledWith('tok-2');
  expect(auth.me?.username).toBe('root');
});
```

- [ ] **Step 2: Run to verify failure**

- [ ] **Step 3: Implement**

`guard.ts` — pure function, exhaustive over `HydrateOutcome`; public routes are `/login` and `/setup`; `offline` renders everywhere including setup.

`auth.svelte.ts` — `hydrate()` calls `get<AuthMe>('/api/auth/me')`; on success sets `me`, `setCsrfToken(me.csrf_token)`, returns `'ready'`. Every `ApiError` branch clears state first, then returns its outcome; unknown errors return `'offline'` and set `error`. `login()` posts, sets CSRF from the response, then hydrates. `logout()` posts `/api/auth/logout`, then `setCsrfToken(null)` and `reset()`.

`login/+page.svelte` — card, disabled while pending, field errors under inputs, inline banner for rate limit (`status 429`, show `Retry-After` if present).

`setup/+page.svelte` — two-step Indonesian wizard: step 1 credentials with confirm and a note that setup runs once; step 2 optional next actions (add bot, add device) with a "Lewati" path that goes to `/`. Step 1 posts `/api/setup`, stores `csrf_token`, hydrates.

`offline-screen.svelte` — "Backend tidak dapat dihubungi", shows `location.origin + '/api/health'`, retry button calling `auth.hydrate()`.

- [ ] **Step 4: Verify and commit**

```bash
npm run test -- --run && npm run check
git add -A frontend && git commit -m "feat(fe): auth store, guards, login and setup"
```

---

### Task 4: Application shell, sidebar, SSE

**Files:**
- Create: `frontend/src/lib/nav.ts`, `frontend/src/lib/components/app-sidebar.svelte`, `frontend/src/lib/components/maintenance-screen.svelte`, `frontend/src/lib/components/connection-badge.svelte`
- Create: `frontend/src/lib/stores/stream.svelte.ts`
- Create: `frontend/src/routes/(app)/+layout.svelte`
- Modify: `frontend/src/routes/+layout.svelte`
- Test: `frontend/src/lib/nav.test.ts`, `frontend/src/lib/stores/stream.test.ts`

**Interfaces:**
- Consumes: `auth`, `guard`, `stream`.
- Produces:
  - `nav.items: NavItem[]` — exactly **12** entries:
    `/` Overview (`devices.view`), `/devices` Devices (`devices.view`),
    `/logs/power` Log Daya (`logs.view`), `/logs/activities` Log Aktivitas (`logs.view`),
    `/logs/errors` Log Error (`logs.view`), `/settings` Settings (`settings.view`),
    `/users` Users (`users.view`), `/telegram-users` Telegram Users (`telegram_users.view`),
    `/roles` Roles (`users.view`), `/bots` Bots (`bots.view`),
    `/backup` Backup (`backup.view`), `/system` System (`system.view`).
  - `nav.visibleItems(can: (p: string) => boolean): NavItem[]`
  - `stream`: `$state devices: Record<number, StreamDevice>` (keyed by **device id**), `connected: boolean`, `lastUpdate: number | null`; `start()`, `stop()`, `reset()`.

- [ ] **Step 1: Write failing tests**

```ts
// src/lib/nav.test.ts
import { nav } from './nav';

it('has exactly 12 entries with unique hrefs', () => {
  expect(nav.items).toHaveLength(12);
  expect(new Set(nav.items.map((i) => i.href)).size).toBe(12);
});

it('hides items whose permission the user lacks', () => {
  const visible = nav.visibleItems((p) => p === 'devices.view');
  expect(visible.map((i) => i.href)).toEqual(['/', '/devices']);
});

it('superadmin sees every entry', () => {
  expect(nav.visibleItems(() => true)).toHaveLength(12);
});
```

```ts
// src/lib/stores/stream.test.ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { stream } from './stream.svelte';

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public url: string) { FakeEventSource.instances.push(this); }
  close() {}
}

beforeEach(() => { vi.useFakeTimers(); vi.stubGlobal('EventSource', FakeEventSource); stream.reset(); });
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); FakeEventSource.instances = []; });

it('keys devices by id', () => {
  stream.start();
  FakeEventSource.instances[0].onmessage?.({
    data: JSON.stringify({ devices: [{ id: 7, name: 'pompa', online: true, power_w: 12 }] }),
  } as MessageEvent);
  expect(stream.devices[7].name).toBe('pompa');
  expect(stream.connected).toBe(true);
});

it('reconnects with growing backoff capped at 30s', () => {
  stream.start();
  FakeEventSource.instances[0].onerror?.();
  expect(stream.connected).toBe(false);
  vi.advanceTimersByTime(1000); expect(FakeEventSource.instances).toHaveLength(2);
  FakeEventSource.instances[1].onerror?.();
  vi.advanceTimersByTime(1999); expect(FakeEventSource.instances).toHaveLength(2);
  vi.advanceTimersByTime(1); expect(FakeEventSource.instances).toHaveLength(3);
});

it('stop cancels reconnection', () => {
  stream.start();
  FakeEventSource.instances[0].onerror?.();
  stream.stop();
  vi.advanceTimersByTime(60_000);
  expect(FakeEventSource.instances).toHaveLength(1);
});
```

- [ ] **Step 2: Run to verify failure**

- [ ] **Step 3: Implement**

`stream.svelte.ts` — one `EventSource('/api/stream')`; `onmessage` parses `StreamSnapshot` and rebuilds `devices` keyed by `id`; on error close, mark disconnected, reconnect `Math.min(30_000, 1000 * 2 ** attempt)`; `stop()` clears the timer and closes.

`+layout.svelte` (root) — runs `auth.hydrate()` once, applies `guard.outcomeToLocation`, renders `offline-screen` or `maintenance-screen` instead of the route tree when those outcomes are returned, otherwise renders `<slot/>`.

`(app)/+layout.svelte` — shadcn `Sidebar.Provider` + collapsible sidebar + header (breadcrumb, theme toggle, connection badge, user dropdown with "Ubah password" and "Keluar"); starts `stream` on mount, stops on destroy; on 401 from any page (`window` event `api:unauthorized` dispatched by a future interceptor in Task 7) resets auth and redirects once.

`connection-badge.svelte` — "terhubung" (green dot) / "terputus" (amber), tooltip shows `lastUpdate`.

- [ ] **Step 4: Verify and commit**

```bash
npm run test -- --run && npm run check
git add -A frontend && git commit -m "feat(fe): app shell, sidebar navigation, sse store"
```

---

### Task 5: Device management

**Files:**
- Create: `frontend/src/routes/(app)/devices/+page.svelte`, `frontend/src/routes/(app)/devices/[id]/+page.svelte`
- Create: `frontend/src/lib/components/device-card.svelte`, `frontend/src/lib/components/device-dialog.svelte`, `frontend/src/lib/components/scan-dialog.svelte`, `frontend/src/lib/components/dps-editor.svelte`, `frontend/src/lib/components/confirm-control.svelte`
- Create: `frontend/src/lib/format.ts`, `frontend/src/lib/devices.ts`
- Test: `frontend/src/lib/format.test.ts`, `frontend/src/lib/devices.test.ts`

**Interfaces:**
- Consumes: `api`, `stream`, `auth`.
- Produces:
  - `format.watts(n: number|null): string`, `format.volts`, `format.amps`, `format.age(seconds|null)`, `format.bytes(n)`, `format.dateTime(iso)`
  - `devices.statusText(status: DeviceStatus): string`
  - `devices.mergeStream(list: Device[], streamDevices: Record<number, StreamDevice>): DeviceView[]`
  - `devices.requiresConfirm(device: Device): boolean` (true when `features.watchdog`)
  - `devices.validation(payload): FieldError[]` — required name/tuya_id/local_key, numeric version.

- [ ] **Step 1: Write failing tests**

```ts
// src/lib/format.test.ts
import { format } from './format';

it('formats power readings with one decimal and a unit', () => {
  expect(format.watts(12.34)).toBe('12.3 W');
  expect(format.watts(0)).toBe('0.0 W');
  expect(format.watts(null)).toBe('--');
});

it('formats ages in Indonesian', () => {
  expect(format.age(5)).toBe('5 detik lalu');
  expect(format.age(120)).toBe('2 menit lalu');
  expect(format.age(7200)).toBe('2 jam lalu');
  expect(format.age(null)).toBe('belum ada data');
});

it('formats bytes', () => {
  expect(format.bytes(2048)).toBe('2.0 KB');
});
```

```ts
// src/lib/devices.test.ts
import { devices } from './devices';

const base = { id: 1, name: 'pompa', label: 'Pompa', type: 'plug', features: {},
  dps: {}, access_roles: [], is_active: true, sort_order: 0, ip: null, version: 3.5,
  last_seen_at: null, last_error: null, has_local_key: true } as const;

it('explains an unreachable device without echoing the raw backend text', () => {
  expect(devices.statusText({ success: false, online: false } as never))
    .toBe('Perangkat tidak merespons. Periksa IP dan local key.');
});

it('merges live stream data over the last fetched list', () => {
  const merged = devices.mergeStream([base as never], {
    1: { id: 1, name: 'pompa', label: 'Pompa', online: true, switch_on: true,
         power_w: 99, voltage_v: 220, current_a: 0.4, age_seconds: 2 },
  });
  expect(merged[0].live?.switch_on).toBe(true);
  expect(merged[0].live?.power_w).toBe(99);
});

it('asks for confirmation when the device has a watchdog', () => {
  expect(devices.requiresConfirm({ ...base, features: { watchdog: true } } as never)).toBe(true);
  expect(devices.requiresConfirm(base as never)).toBe(false);
});

it('reports missing required fields before sending', () => {
  expect(devices.validation({ name: '', tuya_id: '', local_key: '' })).toEqual([
    { key: 'name', message: 'Nama wajib diisi' },
    { key: 'tuya_id', message: 'Tuya ID wajib diisi' },
    { key: 'local_key', message: 'Local key wajib diisi' },
  ]);
});
```

- [ ] **Step 2: Run to verify failure**

- [ ] **Step 3: Implement**

`devices/+page.svelte` — fetch `GET /api/devices`, merge with `stream`, render `device-card` grid. Card: label, name, online dot, switch state, power/voltage/current when mapped, "Nyalakan"/"Matikan" disabled when `!auth.can('devices.control')`; when `requiresConfirm`, open `confirm-control` first. Header: "Tambah device" (`devices.manage`), "Scan LAN" (`devices.scan`). Empty state links to the dialog.

`device-dialog.svelte` — create/edit. Fields: name, label, tuya_id, local_key (password input, placeholder "biarkan kosong untuk mempertahankan" on edit), ip, version, type select (from `/api/devices/templates`), `dps-editor`, `features` checkboxes (`power_logging`, `watchdog`), `access_roles` multi-select. Client validation via `devices.validation`, then server 422 `fieldErrors` mapped onto fields.

`dps-editor.svelte` — semantic key rows (switch/power/current/voltage/brightness/temp/colour) with integer DP inputs, prefilled from the chosen type's template, plus "reset ke template".

`scan-dialog.svelte` — start scan, poll `status !== 'running'` every 1500 ms with a hard stop at 90 s, candidate table, "Gunakan" prefills the device dialog; shows `error` text when `status === 'error'`.

`devices/[id]/+page.svelte` — status card, raw DPS table (from `/status`), "Test koneksi" (`/test`, shows `mapped` vs `dps` so a wrong mapping is visible), edit/delete.

- [ ] **Step 4: Verify and commit**

```bash
npm run test -- --run && npm run check
git add -A frontend && git commit -m "feat(fe): device management, dps editor, scan"
```

---

### Task 6: Dashboard overview

**Files:**
- Create: `frontend/src/routes/(app)/+page.svelte`
- Create: `frontend/src/lib/components/stat-tile.svelte`, `frontend/src/lib/components/power-sparkline.svelte`, `frontend/src/lib/components/recent-activity.svelte`
- Create: `frontend/src/lib/overview.ts`
- Test: `frontend/src/lib/overview.test.ts`

**Interfaces:**
- Consumes: `api`, `stream`, `format`, `auth`.
- Produces: `overview.build({ stats, health, devices, stream, activities })` → `{ tiles, power, activity, alerts }` where:
  - `tiles`: `{ devicesOnline, devicesTotal, powerNow, lastBackup }`
  - `power`: `{ points: {at: string, watts: number}[], current: number|null, max: number }` from `GET /api/logs/power?limit=200` filtered to devices that are on
  - `activity`: first 8 rows of `GET /api/logs/activities?limit=8`
  - `alerts`: array of `{level: 'warn'|'error', text}` built from `health.status !== 'ok'`, any device with `last_error`, and `stream.connected === false`.

- [ ] **Step 1: Write failing tests**

```ts
// src/lib/overview.test.ts
import { overview } from './overview';

const stats = {
  devices: { total: 3, online: 2, offline: 1 },
  rows: {}, database: { path: '/x', size_bytes: 1, schema_version: 4 },
  backup: { last: 'a.db', last_at: '2026-11-18 10:00:00' }, process: { pid: 1 },
} as never;

it('builds the four tiles from stats', () => {
  const model = overview.build({ stats, health: { status: 'ok' }, devices: [], stream: {}, activities: [] });
  expect(model.tiles.devicesOnline).toBe(2);
  expect(model.tiles.devicesTotal).toBe(3);
  expect(model.tiles.lastBackup).toBe('a.db');
});

it('raises an alert when health is not ok or the stream is down', () => {
  const degraded = overview.build({
    stats, health: { status: 'degraded' } as never, devices: [], stream: {}, activities: [],
  });
  expect(degraded.alerts.some((a) => a.level === 'warn')).toBe(true);

  const offlineStream = overview.build({
    stats, health: { status: 'ok' } as never, devices: [], stream: {}, activities: [], connected: false,
  });
  expect(offlineStream.alerts.some((a) => a.text.includes('Realtime'))).toBe(true);
});

it('surfaces the last device error as an alert', () => {
  const model = overview.build({
    stats, health: { status: 'ok' } as never,
    devices: [{ id: 1, label: 'Pompa', last_error: 'Timeout' }] as never,
    stream: {}, activities: [],
  });
  expect(model.alerts).toContainEqual({ level: 'error', text: 'Pompa: Timeout' });
});

it('caps the power series and derives the peak', () => {
  const rows = Array.from({ length: 200 }, (_, i) => ({
    id: i, device_id: 1, power_w: i, voltage_v: 220, current_a: 1,
    switch_state: 1, source: 'periodic', created_at: `2026-11-18 10:${String(i % 60).padStart(2, '0')}:00`,
    device_name: 'pompa', device_label: 'Pompa',
  }));
  const model = overview.build({
    stats, health: { status: 'ok' } as never, devices: [], stream: {}, activities: [], powerRows: rows as never,
  });
  expect(model.power.points.length).toBeLessThanOrEqual(120);
  expect(model.power.max).toBe(199);
});
```

- [ ] **Step 2: Run to verify failure**

- [ ] **Step 3: Implement**

`overview.ts` — pure builder, no fetching.

`(app)/+page.svelte` — parallel `Promise.all` of `GET /api/stats`, `/api/health`, `/api/devices`, `/api/logs/activities?limit=8`, `/api/logs/power?limit=200`; each failure degrades the tile it feeds (never blanks the page), and an `isOffline` failure renders the offline screen. Layout: alert strip, four `stat-tile`s (devices online/total, daya sekarang, backup terakhir, status sistem), `power-sparkline` (inline SVG area + line, peak marker, last-24h labels), quick device grid (reuses `device-card` in compact mode), `recent-activity` list. Quick links to backup/settings gated by permission.

`power-sparkline.svelte` — props `{points, max}`; renders an accessible SVG with `<title>`; empty state "Belum ada data daya".

- [ ] **Step 4: Verify and commit**

```bash
npm run test -- --run && npm run check
git add -A frontend && git commit -m "feat(fe): dashboard overview with tiles, sparkline, alerts"
```

---

### Task 7: Management pages — settings, users, telegram users, roles, bots

**Files:**
- Create: `frontend/src/routes/(app)/settings/+page.svelte`, `.../users/+page.svelte`, `.../telegram-users/+page.svelte`, `.../roles/+page.svelte`, `.../roles/[id]/+page.svelte`, `.../bots/+page.svelte`
- Create: `frontend/src/lib/settings-form.ts`, `frontend/src/lib/permissions.ts`
- Create: `frontend/src/lib/components/setting-field.svelte`, `permission-matrix.svelte`, `role-dialog.svelte`, `bot-dialog.svelte`, `password-dialog.svelte`
- Modify: `frontend/src/lib/api/client.ts` (dispatch `api:unauthorized` on 401 for mutations from the shell)
- Test: `frontend/src/lib/settings-form.test.ts`, `frontend/src/lib/permissions.test.ts`

**Interfaces:**
- Consumes: `api`, `auth`.
- Produces:
  - `settingsForm.fromSchema(schema, values)` → `{ groups, dirtyKeys, set, toPayload, validate, setFieldErrors }`
  - `permissions.groupCatalog(payload)` → `{ name, permissions: { key, label }[] }[]`
  - `permissions.editable(catalog, actorPermissions)` → `string[]`

- [ ] **Step 1: Write failing tests**

```ts
// src/lib/settings-form.test.ts
import { settingsForm } from './settings-form';

const schema = [
  { key: 'a.x', category: 'Alpha', type: 'int', default: 1, minimum: 0, maximum: 10, read_only: false, label: 'X' },
  { key: 'b.y', category: 'Beta', type: 'bool', default: true, read_only: false, label: 'Y' },
  { key: 'a.z', category: 'Alpha', type: 'string', default: 'q', read_only: false, label: 'Z' },
  { key: 'sys.v', category: 'Sistem', type: 'int', default: 9, read_only: true, label: 'V' },
] as never;

it('groups by category in registry order', () => {
  const form = settingsForm.fromSchema(schema, {});
  expect(form.groups.map((g) => g.name)).toEqual(['Alpha', 'Beta', 'Sistem']);
  expect(form.groups[0].fields.map((f) => f.key)).toEqual(['a.x', 'a.z']);
});

it('sends only changed, writable values', () => {
  const form = settingsForm.fromSchema(schema, { 'a.x': 1, 'sys.v': 9 });
  form.set('a.x', 7);
  form.set('sys.v', 10);
  expect(form.toPayload()).toEqual({ 'a.x': 7 });
});

it('validates range before sending', () => {
  const form = settingsForm.fromSchema(schema, { 'a.x': 1 });
  form.set('a.x', 11);
  expect(form.validate()).toEqual([{ key: 'a.x', message: 'Maksimal 10' }]);
});

it('accepts server field errors without losing local edits', () => {
  const form = settingsForm.fromSchema(schema, { 'a.x': 1 });
  form.set('a.x', 5);
  form.setFieldErrors([{ key: 'a.x', message: 'ditolak server' }]);
  expect(form.fields.find((f) => f.key === 'a.x')?.error).toBe('ditolak server');
  expect(form.toPayload()).toEqual({ 'a.x': 5 });
});
```

```ts
// src/lib/permissions.test.ts
import { permissions } from './permissions';

const catalog = {
  categories: [{ name: 'Device', permissions: ['devices.view', 'devices.control'] }],
  all: ['devices.view', 'devices.control', 'roles.manage'],
} as never;

it('labels known keys in Indonesian and falls back to the raw key', () => {
  const grouped = permissions.groupCatalog(catalog);
  const first = grouped[0].permissions[0];
  expect(first.key).toBe('devices.view');
  expect(first.label).toBe('Lihat perangkat');
});

it('offers only permissions the actor already holds', () => {
  expect(permissions.editable(catalog, ['devices.view'])).toEqual(['devices.view']);
});
```

- [ ] **Step 2: Run to verify failure**

- [ ] **Step 3: Implement**

`settings/+page.svelte` — grouped cards from `settingsForm`; `setting-field` per type (bool→switch, int/float→number with min/max, enum→select, string→input, secret→password with "sudah diisi" and never showing a value, json→textarea with JSON parse check); `apply` badge ("langsung" / "restart bot"); read-only disabled with "khusus sistem"; sticky save bar with change count; PATCH then map 422 errors back.

`users/+page.svelte` — table (username, role, aktif, login terakhir); create/edit dialog; password reset via `password-dialog` (current+new for self, admin-set for others); deactivate toggle; a 409 "last manager" response is rendered as a blocking explanation on that row, not a toast.

`telegram-users/+page.svelte` — table (`telegram_id`, label, role, aktif); add form with numeric validation; role select limited by `permissions.editable`; inline note that these accounts cannot log into the web UI.

`roles/+page.svelte` + `[id]` — list with permission/user counts; editor uses `permission-matrix` (grouped checkboxes, "pilih semua", protected keys disabled with a lock and tooltip "izin inti role terlindungi"); a banner warns that saving revokes sessions of affected users.

`bots/+page.svelte` — cards with label, `@username`, runtime status, `last_error` (monospace, clamped with expand), enable/disable switch, "Uji", "Ganti token" (write-only, explicit note it cannot be read back), delete with typed label confirmation.

`client.ts` addition — when a request made through the shell receives 401, dispatch `window.dispatchEvent(new CustomEvent('api:unauthorized'))`; the shell resets auth and redirects to `/login` once (guarded by a flag so parallel failures do not loop).

- [ ] **Step 4: Verify and commit**

```bash
npm run test -- --run && npm run check
git add -A frontend && git commit -m "feat(fe): settings, users, telegram users, roles and bots"
```

---

### Task 8: Monitoring — power, activity, error, audit logs, system health

**Files:**
- Create: `frontend/src/routes/(app)/logs/power/+page.svelte`, `.../logs/activities/+page.svelte`, `.../logs/errors/+page.svelte`, `.../system/+page.svelte`
- Create: `frontend/src/lib/components/log-table.svelte`, `frontend/src/lib/components/device-filter.svelte`, `frontend/src/lib/components/audit-table.svelte`, `frontend/src/lib/components/health-cards.svelte`
- Create: `frontend/src/lib/log-table.ts`
- Test: `frontend/src/lib/log-table.test.ts`, `frontend/src/lib/audit.test.ts`

**Interfaces:**
- Consumes: `api`, `format`, `stream`.
- Produces:
  - `logTable.rows<T>(fetcher, {limit, deviceId})` → `{ items, loading, error, hasNext, load, next, prev, setDevice }`; page shape `{ items, limit, offset }` from the backend.
  - `audit.filters(q)` → `URLSearchParams` covering `actor_kind`, `action`, `result`, `target_kind`, `since`, `until`, `limit`, `offset`.

- [ ] **Step 1: Write failing tests**

```ts
// src/lib/log-table.test.ts
import { logTable } from './log-table';

it('pages with a fixed size and stops at an empty page', async () => {
  const calls: string[] = [];
  const fetcher = async (path: string) => {
    calls.push(path);
    return { items: path.includes('offset=50') ? [] : [{ id: 1 }], limit: 50, offset: 0 };
  };
  const table = logTable.rows<{ id: number }>(fetcher, { limit: 50 });
  await table.load();
  expect(table.items).toHaveLength(1);
  await table.next();
  expect(calls[1]).toContain('offset=50');
  expect(table.hasNext).toBe(false);
});

it('changing the device filter resets to the first page', async () => {
  const calls: string[] = [];
  const fetcher = async (path: string) => { calls.push(path); return { items: [{ id: 1 }], limit: 50, offset: 0 }; };
  const table = logTable.rows<{ id: number }>(fetcher, { limit: 50 });
  await table.load();
  await table.next();
  await table.setDevice(3);
  expect(calls.at(-1)).toContain('offset=0');
  expect(calls.at(-1)).toContain('device_id=3');
});
```

```ts
// src/lib/audit.test.ts
import { audit } from './audit';

it('omits empty filters and encodes values', () => {
  const params = audit.filters({ result: 'denied', action: 'access.denied', actor_kind: '', limit: 50 });
  expect(params.toString()).toBe('action=access.denied&result=denied&limit=50');
});
```

- [ ] **Step 2: Run to verify failure**

- [ ] **Step 3: Implement**

Three log pages share `log-table` with page-specific columns; each has `device-filter` populated from `GET /api/devices`, empty states in Indonesian, and 50-row pages. Power page also renders `power-sparkline` for the loaded window. Errors page shows an expandable trace in a `<pre>` with `textContent` (never `{@html}`).

`system/+page.svelte` — `health-cards` (status, database, devices fresh/total, maintenance), stats block (DB path/size/schema version, row counts, last backup), maintenance toggle (reason + auto-off minutes, confirmation), and `audit-table` with the filters from `audit.filters`, a details drawer rendering JSON, and pagination. Audit page is hidden for users without `audit.view`.

- [ ] **Step 4: Verify and commit**

```bash
npm run test -- --run && npm run check
git add -A frontend && git commit -m "feat(fe): log pages, audit table, system health"
```

---

### Task 9: Backup, container, nginx, CI, docs, integration smoke

**Files:**
- Create: `frontend/src/routes/(app)/backup/+page.svelte`
- Create: `frontend/src/lib/components/restore-dialog.svelte`, `frontend/src/lib/backup-form.ts`
- Create: `frontend/Dockerfile`, `frontend/nginx.conf`, `frontend/.dockerignore`
- Create: `.github/workflows/frontend.yml`
- Create: `frontend/README.md`, `frontend/src/lib/api/integration.test.ts`
- Modify: root `docker-compose.yml`, root `README.md`
- Test: `frontend/src/lib/backup-form.test.ts`, `frontend/src/lib/api/integration.test.ts`

**Interfaces:**
- Consumes: everything.
- Produces: `docker compose up` serving the dashboard on `:8080`-adjacent port with `/api` proxied to the backend container.

- [ ] **Step 1: Write failing tests**

```ts
// src/lib/backup-form.test.ts
import { backupForm } from './backup-form';

it('requires a password and the literal RESTORE before it is valid', () => {
  const form = backupForm.restore();
  expect(form.valid).toBe(false);
  form.setPassword('rahasia');
  form.setConfirm('bukan');
  expect(form.valid).toBe(false);
  form.setConfirm('restore');
  expect(form.valid).toBe(true);
  expect(form.toFormData().get('confirm')).toBe('RESTORE');
});

it('refuses a file over 200 MB before uploading', () => {
  const form = backupForm.restore();
  expect(form.setFile(new File([new Uint8Array(201 * 1024 * 1024)], 'big.db'))).toBe(
    'Ukuran file maksimal 200 MB',
  );
});
```

```ts
// src/lib/api/integration.test.ts — runs against a live backend; skipped when absent
import { describe, expect, it } from 'vitest';
import { api, setCsrfToken } from './client';

const base = process.env.VITE_TEST_API ?? '';
const enabled = Boolean(base);

describe.skipIf(!enabled)('backend integration', () => {
  it('reports setup status without a session', async () => {
    const status = await api<{ required: boolean }>(`${base}/api/setup/status`);
    expect(typeof status.required).toBe('boolean');
  });

  it('rejects an unauthenticated protected route with 401', async () => {
    await expect(api(`${base}/api/settings`)).rejects.toMatchObject({ status: 401 });
  });

  it('rejects a mutation without CSRF once authenticated', async () => {
    const login = await api<{ csrf_token: string }>(`${base}/api/auth/login`, {
      method: 'POST', body: { username: 'root', password: 'password-panjang' },
    });
    setCsrfToken(null);
    await expect(api(`${base}/api/settings`, { method: 'PATCH', body: { values: { 'ui.title': 'X' } } }))
      .rejects.toMatchObject({ status: 403 });
    setCsrfToken(login.csrf_token);
    await expect(api(`${base}/api/auth/me`)).resolves.toMatchObject({ username: 'root' });
  });
});
```

- [ ] **Step 2: Run to verify failure**

- [ ] **Step 3: Implement backup page and restore dialog**

`backup/+page.svelte` — table (filename, kind badge auto/manual/pre_restore, size, created_at), "Buat backup" (`backup.create`), download (`backup.restore` permission, warning "berisi seluruh data termasuk rahasia"), and "Restore" opening `restore-dialog`.

`restore-dialog.svelte` — file picker, password, typed `RESTORE`, warnings that the app enters maintenance and sessions are revoked; uploads `FormData` to `/api/backup/restore`; a 422 with `stage` renders the stage in Indonesian (`integrity` → "file rusak", `version` → "backup dari versi lebih baru", `swap` → "gagal menukar database") and tells the operator maintenance stays on.

- [ ] **Step 4: Implement deployment**

`nginx.conf` — `location /api/ { proxy_pass http://backend:8080; proxy_set_header Host $host; proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; proxy_buffering off; }` (buffering off is required for SSE), `location / { try_files $uri /index.html; }`, `add_header Cache-Control "no-store"` for `index.html`.
`Dockerfile` — `node:24-alpine` build stage (`npm ci && npm run build`), `nginx:alpine` runtime.
Root `docker-compose.yml` — add a `frontend` service publishing `8080:80`, `depends_on: [backend]`, on the default bridge network (it reaches backend by service name; the backend keeps `network_mode: host` for Tuya discovery).
`.github/workflows/frontend.yml` — `working-directory: frontend`, `npm ci`, `npm run check`, `npm run test -- --run`, `npm run build`.
`frontend/README.md` — dev setup, env, scripts, note that the backend is required.

- [ ] **Step 5: Verify**

```bash
cd frontend
npm run test -- --run && npm run check && npm run build
cd ..
git add -A && git commit -m "feat(fe): backup and restore, container, nginx, ci"
```

- [ ] **Step 6: End-to-end smoke (manual, backend must run)**

```bash
# terminal 1
cd backend && PYTHONPATH=src python -m tuyabot.main
# terminal 2
cd frontend && npm run dev
```

Expected: `/setup` completes → overview loads (tiles filled, alerts empty) → device created via dialog → toggle works and the card updates through SSE → settings save → role editor shows permissions → backup row appears → system shows `ok`/`degraded`. Then stop the backend: every page shows the offline screen, not a blank table.

- [ ] **Step 7: Run the integration test against the live backend**

```bash
cd frontend && VITE_TEST_API=http://127.0.0.1:8080 npm run test -- --run src/lib/api/integration.test.ts
```

Expected: 3 passed when the backend is set up; skipped when `VITE_TEST_API` is unset (so CI without a backend stays green).

---

## Self-Review Notes

- Nav count is now pinned to 12 by a test (`nav.test.ts`), matching the list in Task 4.
- `HydrateOutcome` includes `offline`; `guard.outcomeToLocation` is exhaustive and tested.
- The stream store keys by device `id` (the backend sends both `id` and `name`); tests assert the id.
- `ApiInit` covers `FormData` (no manual `Content-Type`) and `download()` covers binary bodies; both tested.
- OpenAPI type generation is **not** used: the backend sets `openapi_url=None` and declares no `response_model`, so the generated schema would be empty. Types are transcribed from the verified route contract at the top of this plan. If the backend later adopts `response_model`, generating types becomes a small follow-up, not a rewrite.
- Dashboard overview has its own milestone (Task 6) with a pure builder and four tests, placed immediately after device management.
- Integration coverage: `integration.test.ts` exercises setup-status, unauthenticated 401, and CSRF-on/off against a live backend, opt-in through `VITE_TEST_API`.

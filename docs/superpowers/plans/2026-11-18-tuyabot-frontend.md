# Zen Tuyabot Frontend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the dashboard SPA that drives the existing Zen Tuyabot backend: setup wizard, login, overview, devices, logs, settings, users, roles, bots, backup, and system pages behind a sidebar shell.

**Architecture:** SvelteKit SPA (SSR disabled, `adapter-static` + `index.html` fallback) behind nginx. A thin HTTP core (`api/client.ts`) owns cookies, CSRF, response parsing, error normalization, and central 401 handling; per-domain modules (`api/devices.ts`, `api/roles.ts`, …) expose typed functions. Auth state is a runes store hydrated from `/api/auth/me`, with an explicit refresh path so permission changes take effect without re-login. Backend reachability and SSE connectivity are tracked separately.

**Tech Stack:** SvelteKit 3.x, Svelte 5 (runes), TypeScript, Tailwind CSS 4, shadcn-svelte 1.x, clsx + tailwind-merge, mode-watcher, svelte-sonner, Vitest + @testing-library/svelte, svelte-check.

**Spec:** `docs/superpowers/specs/2026-11-17-tuyabot-rebuild-design.md` (§7.2, §8.15, §8.16)

## Global Constraints

- Monorepo root `zen-tuyabot/`; this plan writes only inside `frontend/`.
- Backend is required. No mock server, no MSW. Unreachable `/api` shows an offline screen with retry — never fake data.
- Node 24, npm 11.
- Svelte 5 runes only. No `export let`, no `svelte/store` in new code.
- UI copy Indonesian, English technical terms kept verbatim ("Settings", "Backup", "Role", "Permission", "Device", "Bot", "Restore", "Maintenance", "Audit log", "Scan", "DPS"). API field names never translated.
- Mutations send `X-CSRF-Token`; GET never does.
- No credentials in `localStorage`. Session is an HttpOnly cookie; the CSRF token lives in memory only.
- All failures surface as `ApiError`. Never render backend text as HTML.
- `npm run check` and `npm run test` pass at the end of every task.
- **Every endpoint used by a page appears in the contract block below, verified against `backend/src/tuyabot/web/routes/`.** Implementers must not guess endpoints.

---

## Verified backend contract

Paths are relative to the API origin. Every route except the public ones requires a session cookie (or `X-API-Key`) and the listed permission.

### Public

| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/api/setup/status` | — | `{ required, steps_done: { admin } }` |
| POST | `/api/setup` | `{ username, password }` | `{ authenticated, user_id, csrf_token }` + cookies. 409 if already done |
| GET | `/api/auth/csrf` | — | `{ csrf_token }` + `csrf_token` cookie |
| POST | `/api/auth/login` | `{ username, password }` | `{ authenticated, user_id, csrf_token }` + cookies. 401 bad credentials, 429 rate limited (+`Retry-After`) |
| GET | `/healthz` | — | `{ status: "ok" }` (no auth, no DB) |

### Auth

| Method | Path | Body | Permission / notes |
|---|---|---|---|
| POST | `/api/auth/logout` | — | session; revokes it |
| GET | `/api/auth/me` | — | session → `{ id, username, actor_kind, role:{id,slug,name}\|null, permissions[], csrf_token }` |
| POST | `/api/auth/password` | `{ current_password, new_password }` | web only; revokes other sessions |
| GET | `/api/auth/sessions` | — | web only → `{ sessions: [{token_hash, created_at, expires_at, last_seen_at, ip, user_agent, revoked_at, is_current}] }` |
| DELETE | `/api/auth/sessions/{session_id}` | — | web only → `{ revoked }` |

### Devices

| Method | Path | Body | Permission |
|---|---|---|---|
| GET | `/api/devices` | — | `devices.view`; filtered by `access_roles` (holders of `devices.manage` see all) |
| GET | `/api/devices/templates` | — | `devices.view` → `{ templates, types, features }` |
| POST | `/api/devices` | `{ name, label?, tuya_id, local_key, ip?, version?, type?, dps?, features?, access_roles?, is_active?, sort_order? }` | `devices.manage` |
| PATCH | `/api/devices/{id}` | any subset of the above, plus `local_key` | `devices.manage` |
| DELETE | `/api/devices/{id}` | — | `devices.manage` |
| POST | `/api/devices/{id}/on` \| `/off` | — | `devices.control` + visibility |
| GET | `/api/devices/{id}/status` | — | `devices.view` + visibility |
| POST | `/api/devices/{id}/test` | — | `devices.scan` |
| POST | `/api/devices/scan` | — | `devices.scan`; 409 if a scan is already running |
| GET | `/api/devices/scan/{job_id}` | — | `devices.scan` |

Device object: `{ id, name, label, type, ip, version, dps, features, access_roles, is_active, sort_order, last_seen_at, last_error, has_local_key }`. `local_key`/`tuya_id` are never returned.
Device create/update errors: `422 { detail: { errors: [{ key, message }] } }` with `key` in `name|type|dps|features|access_roles|tuya_id`.

### Logs, settings, stream, stats

| Method | Path | Query / body | Permission |
|---|---|---|---|
| GET | `/api/logs/activities` | `limit` (≤200), `offset`, `device_id` | `logs.view` |
| GET | `/api/logs/power` | `limit`, `offset`, `device_id` | `logs.view` |
| GET | `/api/logs/errors` | `limit`, `offset` | `logs.view` |
| GET | `/api/settings` | — | `settings.view` → `{ values, schema }` |
| GET | `/api/settings/schema` | — | `settings.view` |
| PATCH | `/api/settings` | `{ values: Record<string, unknown> }` | `settings.edit`; 422 `detail.errors[]` |
| GET | `/api/stream` | — | `devices.view`; SSE `{ ts, devices: [{ id, name, label, online, switch_on, power_w, voltage_v, current_a, age_seconds }] }` |
| GET | `/api/stats` | — | `system.view` |
| GET | `/api/health` | — | session → `{ status, database, devices_total, devices_fresh, maintenance }` |
| GET | `/api/maintenance/status` | — | session → `{ maintenance }` |
| GET | `/api/maintenance` | — | `system.view` → `{ maintenance, state }` |
| POST | `/api/maintenance` | `{ enabled: bool, reason?, auto_off_minutes? }` | `system.maintenance` |
| GET | `/api/audit` | `limit, offset, actor_kind, action, result, target_kind, request_id, since, until` | `audit.view` → `{ items, limit, offset }` |

### Roles

| Method | Path | Body | Permission |
|---|---|---|---|
| GET | `/api/roles` | — | `users.view` → `{ roles: Role[] }` where `Role = { id, slug, name, description, permissions[], rate_limit_per_minute, is_system, is_protected, user_count }` |
| GET | `/api/roles/permissions` | — | `users.view` → `{ categories: [{name, permissions[]}], all[] }` |
| POST | `/api/roles` | `{ slug, name, description?, permissions[] }` | `roles.manage`; 403 if granting a permission the actor lacks; 409 duplicate slug |
| PATCH | `/api/roles/{id}` | `{ name?, description?, permissions?, rate_limit_per_minute? }` | `roles.manage`; 409 when removing a protected role's required permissions; revokes affected sessions and API keys |
| DELETE | `/api/roles/{id}` | — | `roles.manage`; 409 `{ detail: { message, references: {web_users, telegram_users, api_keys, devices} } }` when still used |

### Web users

| Method | Path | Body | Permission |
|---|---|---|---|
| GET | `/api/web-users` | — | `users.view` → `{ users: [{ id, username, role_id, is_active, created_by, created_at, updated_at, last_login_at, role:{id,slug,name} }] }` |
| POST | `/api/web-users` | `{ username, password, role_id }` | `users.manage`; 403 higher role; 422 duplicate/weak password |
| PATCH | `/api/web-users/{id}` | `{ password?, role_id?, is_active? }` | `users.manage`; 403 higher role; 409 last `users.manage` holder; revokes that user's sessions on any change |
| DELETE | `/api/web-users/{id}` | — | `users.manage`; 403/409 guards as above |

### Telegram users (separate entity; no login)

| Method | Path | Body | Permission |
|---|---|---|---|
| GET | `/api/telegram-users` | — | `telegram_users.view` → `{ telegram_users: [{ telegram_id, label, role_id, is_active, role_slug, role_name, created_at, updated_at, last_seen_at }] }` |
| POST | `/api/telegram-users` | `{ telegram_id: int, label?, role_id }` | `telegram_users.manage`; 422 non-integer id; 403 higher role |
| PATCH | `/api/telegram-users/{telegram_id}` | `{ label?, role_id?, is_active? }` | `telegram_users.manage` |
| DELETE | `/api/telegram-users/{telegram_id}` | — | `telegram_users.manage` |

### Bots

| Method | Path | Body | Permission |
|---|---|---|---|
| GET | `/api/bots` | — | `bots.view` → `{ bots: [{ id, label, enabled, bot_username, last_ok_at, last_error, runtime_status }] }` (never the token) |
| POST | `/api/bots` | `{ label, token }` | `bots.manage`; 409 duplicate token |
| PATCH | `/api/bots/{id}` | `{ label?, token?, enabled? }` | `bots.manage`; token change triggers a rebuild |
| POST | `/api/bots/{id}/enable` \| `/disable` | — | `bots.manage` → `{ status }` |
| POST | `/api/bots/{id}/test` | — | `bots.manage` → `{ ok, username?, message? }` |
| DELETE | `/api/bots/{id}` | — | `bots.manage` |

### Backup

| Method | Path | Body | Permission |
|---|---|---|---|
| GET | `/api/backup` | — | `backup.view` → `{ backups: [{ id, filename, size_bytes, kind, note, created_at }] }` |
| POST | `/api/backup` | — | `backup.create` → `{ id, filename, path, size_bytes }` |
| GET | `/api/backup/{id}/download` | — | `backup.restore`; binary (`application/octet-stream`) |
| POST | `/api/backup/restore` | **multipart** `file`, `password`, `confirm` (must be `RESTORE`) | `system.restore` + web account; 422 `{ detail: { stage, message, maintenance } }` with `stage` in `upload\|integrity\|schema\|version\|swap`; enters and (on success) leaves maintenance |

### Error shapes to implement against

```jsonc
422 { "detail": { "errors": [{ "key": "name", "message": "..." }] } }   // field errors
422 { "detail": { "stage": "version", "message": "...", "maintenance": true } }
409 { "detail": "Role masih dipakai", "references": { ... } } | { "detail": "setup_required", "setup_required": true }
423/503 { "detail": "maintenance", "message": "...", "retry_after": 60 }
```


## Review Focus

1. **Backend down** — offline screen with retry; no empty table that looks like "no data". (Task 2, Task 3)
2. **Session expires mid-use** — one central 401 path, one redirect, no loop, and a failed login 401 must **not** trigger it. (Task 2)
3. **CSRF token lost on reload** — hydrate runs before any mutation can fire. (Task 3)
4. **Maintenance on** — maintenance screen, not a toast per page; the app can still log out. (Task 3)
5. **Permission revoked while logged in** — refresh path after role/user mutations and on 403, so stale buttons disappear. (Task 7)
6. **SSE drops while the API is fine** — a badge, not the offline screen. (Task 5)

---

## Milestones

| # | Milestone | Tasks |
|---|---|---|
| 0 | Contract audit | done — captured above |
| 1 | Foundation | 1 |
| 2 | API layer | 2 |
| 3 | Authentication | 3 |
| 4 | Application shell | 4 |
| 5 | Device management | 5 |
| 6 | Dashboard overview | 6 |
| 7 | Management pages | 7 |
| 8 | Monitoring | 8 |
| 9 | Backup, static build, external nginx, CI | 9 |

---

### Task 1: Scaffold SvelteKit, Tailwind 4, shadcn-svelte, dev proxy

**Files:** `frontend/package.json`, `svelte.config.js`, `vite.config.ts`, `tsconfig.json`, `src/app.html`, `src/app.css`, `src/routes/+layout.ts`, `src/routes/+layout.svelte`, `src/routes/+page.svelte`, `components.json`, `vitest.config.ts`, `vitest-setup.ts`, `src/lib/utils.ts`, `.env.example`. Test: `src/lib/utils.test.ts`.

**Interfaces:** produces dev server on 5173 with `/api` → 8080; `cn(...)`; scripts `dev|build|check|test`.

- [ ] **Step 1: Create and install**

```bash
cd "D:/Datas/MyData/Project Repo/zen-tuyabot"
npx sv create frontend --template minimal --types ts --no-add-ons --install npm
cd frontend
npm i -D @sveltejs/adapter-static tailwindcss @tailwindcss/vite vitest jsdom \
      @testing-library/svelte @testing-library/jest-dom svelte-check
npm i clsx tailwind-merge mode-watcher svelte-sonner
npx shadcn-svelte@latest init      # default, neutral, CSS variables
npx shadcn-svelte@latest add button input label card table dialog alert-dialog select \
      switch tabs badge sidebar sheet dropdown-menu skeleton separator tooltip sonner \
      checkbox textarea progress
```

`clsx` and `tailwind-merge` are installed explicitly: `shadcn-svelte init` generates `cn()` but does not always add both dependencies.

- [ ] **Step 2: Configure SPA output, proxy, vitest**

`svelte.config.js`: `adapter-static`, `fallback: 'index.html'`.
`src/routes/+layout.ts`: `ssr = false; prerender = false;`.
`vite.config.ts`: `server.proxy['/api'] = { target: 'http://127.0.0.1:8080', changeOrigin: false }` (keeps `Host` equal to the browser origin for the backend's `Origin` check); `test = { environment: 'jsdom', setupFiles: ['./vitest-setup.ts'], include: ['src/**/*.test.ts'] }`.
`.env.example`: `PUBLIC_API_BASE=` — empty means same-origin via proxy.

- [ ] **Step 3: Failing test**

```ts
// src/lib/utils.test.ts
import { describe, expect, it } from 'vitest';
import { cn } from './utils';

it('joins truthy classes and drops falsy ones', () => {
  expect(cn('a', false && 'b', undefined, 'c')).toBe('a c');
});

it('lets a later tailwind class win', () => {
  expect(cn('p-2', 'p-4')).toBe('p-4');
});
```

- [ ] **Step 4: Verify failure** — `npm run test -- --run src/lib/utils.test.ts` → cannot resolve `./utils`.

- [ ] **Step 5: Implement `cn`** in `src/lib/utils.ts` with `clsx` + `twMerge`.

- [ ] **Step 6: Verify and commit**

```bash
npm run test -- --run && npm run check && npm run build
git add -A frontend && git commit -m "feat(fe): scaffold sveltekit, tailwind, shadcn-svelte"
```

---

### Task 2: HTTP core, error model, domain modules, central 401

**Files:**
- Create: `src/lib/api/errors.ts`, `client.ts`, `types.ts`, `index.ts`
- Create: `src/lib/api/auth.ts`, `devices.ts`, `logs.ts`, `settings.ts`, `users.ts`, `roles.ts`, `bots.ts`, `backup.ts`, `system.ts`
- Test: `src/lib/api/errors.test.ts`, `src/lib/api/client.test.ts`, `src/lib/api/domains.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `class ApiError extends Error { status; detail; fieldErrors: FieldError[]; stage?: string; isSetupRequired; isMaintenance; isOffline }`, `toApiError(response)`, `toApiError.offline()`.
  - `setCsrfToken(t: string | null)`.
  - `api<T>(path, init?: { method?; body?; form?: FormData; signal?; silent401?: boolean }): Promise<T>`.
  - `download(path, filename): Promise<void>`.
  - `onUnauthorized(cb: (() => void) | null): void`; the client calls it on **any** 401 (GET or mutation) **unless** `path` is one of `/api/auth/login`, `/api/auth/csrf`, `/api/setup`, `/api/setup/status`, or `silent401: true`.
  - Domain modules (thin, typed): `authApi.{me,login,logout,changePassword,sessions,revokeSession,csrf}`, `devicesApi.{list,templates,create,update,remove,on,off,status,test,scan,scanStatus}`, `logsApi.{activities,power,errors}`, `settingsApi.{get,schema,patch}`, `usersApi.{list,create,update,remove}`, `telegramUsersApi.{list,create,update,remove}`, `rolesApi.{list,catalog,create,update,remove}`, `botsApi.{list,create,update,enable,disable,test,remove}`, `backupApi.{list,create,download,restore}`, `systemApi.{stats,health,maintenanceStatus,maintenance,setMaintenance,audit}`.
  - All types from the contract block.

- [ ] **Step 1: Failing tests**

```ts
// src/lib/api/errors.test.ts
import { toApiError } from './errors';

it('reads field errors', async () => {
  const err = await toApiError(new Response(JSON.stringify({ detail: { errors: [{ key: 'name', message: 'wajib' }] } }), { status: 422 }));
  expect(err.fieldErrors).toEqual([{ key: 'name', message: 'wajib' }]);
});

it('reads the restore stage', async () => {
  const err = await toApiError(new Response(
    JSON.stringify({ detail: { stage: 'version', message: 'lebih baru', maintenance: true } }), { status: 422 }));
  expect(err.stage).toBe('version');
});

it('never turns an HTML error page into the message', async () => {
  const err = await toApiError(new Response('<html>502 Bad Gateway</html>', { status: 502 }));
  expect(err.detail).toBe('Bad Gateway');
});

it('flags setup, maintenance and offline', async () => {
  expect((await toApiError(new Response(JSON.stringify({ setup_required: true }), { status: 409 }))).isSetupRequired).toBe(true);
  expect((await toApiError(new Response(JSON.stringify({ detail: 'maintenance', message: 'mt' }), { status: 503 }))).isMaintenance).toBe(true);
  expect(toApiError.offline()).toMatchObject({ status: 0, isOffline: true });
});
```

```ts
// src/lib/api/client.test.ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api, download, onUnauthorized, setCsrfToken } from './client';

function mockFetch(response: Response) {
  const spy = vi.fn().mockResolvedValue(response);
  vi.stubGlobal('fetch', spy);
  return spy;
}

beforeEach(() => { setCsrfToken(null); onUnauthorized(null); });
afterEach(() => vi.unstubAllGlobals());

it('sends credentials and csrf on mutations', async () => {
  const spy = mockFetch(new Response('{}', { status: 200 }));
  setCsrfToken('abc');
  await api('/api/devices', { method: 'POST', body: { name: 'x' } });
  const [, init] = spy.mock.calls[0];
  expect(init.credentials).toBe('same-origin');
  expect(init.headers['X-CSRF-Token']).toBe('abc');
  expect(init.body).toBe('{"name":"x"}');
});

it('omits csrf on GET', async () => {
  const spy = mockFetch(new Response('{}', { status: 200 }));
  setCsrfToken('abc');
  await api('/api/devices');
  expect(spy.mock.calls[0][1].headers['X-CSRF-Token']).toBeUndefined();
});

it('leaves Content-Type to the browser for FormData', async () => {
  const spy = mockFetch(new Response('{}', { status: 200 }));
  const form = new FormData();
  await api('/api/backup/restore', { method: 'POST', form });
  expect(spy.mock.calls[0][1].headers['Content-Type']).toBeUndefined();
});

it('returns undefined for empty bodies', async () => {
  mockFetch(new Response(null, { status: 204 }));
  await expect(api('/api/x', { method: 'DELETE' })).resolves.toBeUndefined();
});

it('maps a fetch rejection to offline, and only a fetch rejection', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
  await expect(api('/api/devices')).rejects.toMatchObject({ isOffline: true });

  // A JSON parse failure must NOT be reported as offline.
  mockFetch(new Response('{not json', { status: 200 }));
  await expect(api('/api/devices')).resolves.toBeUndefined();
});

it('calls the 401 handler for protected routes on GET and mutations', async () => {
  const handler = vi.fn();
  onUnauthorized(handler);
  mockFetch(new Response('{}', { status: 401 }));
  await expect(api('/api/settings')).rejects.toMatchObject({ status: 401 });
  await expect(api('/api/devices', { method: 'POST', body: {} })).rejects.toMatchObject({ status: 401 });
  expect(handler).toHaveBeenCalledTimes(2);
});

it('does not call the 401 handler for login, setup or csrf', async () => {
  const handler = vi.fn();
  onUnauthorized(handler);
  mockFetch(new Response('{}', { status: 401 }));
  for (const path of ['/api/auth/login', '/api/setup', '/api/auth/csrf', '/api/setup/status']) {
    await expect(api(path, { method: 'POST', body: {} })).rejects.toMatchObject({ status: 401 });
  }
  expect(handler).not.toHaveBeenCalled();
});

it('honours silent401', async () => {
  const handler = vi.fn();
  onUnauthorized(handler);
  mockFetch(new Response('{}', { status: 401 }));
  await expect(api('/api/auth/me', { silent401: true })).rejects.toMatchObject({ status: 401 });
  expect(handler).not.toHaveBeenCalled();
});

it('downloads via blob url', async () => {
  mockFetch(new Response(new Blob(['d']), { status: 200 }));
  const createObjectURL = vi.fn().mockReturnValue('blob:x');
  const revokeObjectURL = vi.fn();
  vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL });
  const click = vi.fn();
  vi.spyOn(document, 'createElement').mockReturnValue({ click, href: '', download: '' } as never);
  await download('/api/backup/1/download', 'a.db');
  expect(revokeObjectURL).toHaveBeenCalledWith('blob:x');
  expect(click).toHaveBeenCalled();
});
```

```ts
// src/lib/api/domains.test.ts — verifies each module hits the documented path/method
import { api } from './client';
import { backupApi, botsApi, devicesApi, rolesApi, telegramUsersApi, usersApi } from './index';
import { vi } from 'vitest';

vi.mock('./client', () => ({ api: vi.fn().mockResolvedValue({}), download: vi.fn(), setCsrfToken: vi.fn() }));

it('web users use /api/web-users', async () => {
  await usersApi.create({ username: 'a', password: 'b', role_id: 1 });
  expect(api).toHaveBeenCalledWith('/api/web-users', { method: 'POST', body: { username: 'a', password: 'b', role_id: 1 } });
  await usersApi.update(3, { is_active: false });
  expect(api).toHaveBeenCalledWith('/api/web-users/3', { method: 'PATCH', body: { is_active: false } });
});

it('telegram users use their own path and integer id', async () => {
  await telegramUsersApi.remove(555);
  expect(api).toHaveBeenCalledWith('/api/telegram-users/555', { method: 'DELETE' });
});

it('bots expose enable/disable/test', async () => {
  await botsApi.enable(2);
  expect(api).toHaveBeenCalledWith('/api/bots/2/enable', { method: 'POST' });
  await botsApi.test(2);
  expect(api).toHaveBeenCalledWith('/api/bots/2/test', { method: 'POST' });
});

it('roles use the catalog endpoint', async () => {
  await rolesApi.catalog();
  expect(api).toHaveBeenCalledWith('/api/roles/permissions');
});

it('devices scan polls by job id', async () => {
  await devicesApi.scanStatus('ab12');
  expect(api).toHaveBeenCalledWith('/api/devices/scan/ab12');
});

it('backup restore posts multipart', async () => {
  const form = new FormData();
  await backupApi.restore(form);
  expect(api).toHaveBeenCalledWith('/api/backup/restore', { method: 'POST', form });
});
```

- [ ] **Step 2: Verify failure** — modules missing.

- [ ] **Step 3: Implement**

`client.ts`:
```
fetch call wrapped ALONE in try/catch -> ApiError.offline()
response.ok?  parse: no body -> undefined; JSON when content-type is json; else text.
!response.ok -> build ApiError; if status===401 and path not public and !silent401 -> unauthorizedHandler?.()
```
The `try/catch` covers **only** the `fetch(...)` expression; body parsing sits outside it, so a malformed JSON body is never reported as "backend offline".

`errors.ts`: JSON only when `content-type` includes `application/json`; `detail = body.message ?? body.detail ?? statusText`; `fieldErrors` from `body.detail.errors` or `[]`; `stage` from `body.detail.stage`; `isSetupRequired` on 409 + flag; `isMaintenance` on 503 or `detail === 'maintenance'`.

Domain modules: one exported object per domain, each function delegating to `api` with the exact path from the contract. No logic beyond argument shaping.

- [ ] **Step 4: Verify and commit**

```bash
npm run test -- --run && npm run check
git add -A frontend && git commit -m "feat(fe): http core, central 401, typed domain api modules"
```

---

### Task 3: Auth store, login, setup wizard, theme

**Files:** `src/lib/stores/auth.svelte.ts`, `src/lib/stores/theme.svelte.ts`, `src/lib/guard.ts`, `src/routes/login/+page.svelte`, `src/routes/setup/+page.svelte`, `src/lib/components/theme-toggle.svelte`, `offline-screen.svelte`, `src/routes/+layout.svelte`. Tests: `src/lib/guard.test.ts`, `src/lib/stores/auth.test.ts`.

**Interfaces:**
- `type HydrateOutcome = 'ready' | 'login' | 'setup' | 'maintenance' | 'offline'`
- `auth`: `me`, `loading`, `error`, `hydrate()`, `login(u,p)`, `logout()`, `refresh()`, `can()`, `canAny()`, `reset()`.
- `guard.outcomeToLocation(outcome, pathname) -> { redirect?: string; render?: 'offline'|'maintenance' }`

**Where the CSRF token comes from:** `/api/auth/me` returns one bound to the current session, and `login`/`setup` return one bound to the session they just created. Both are consumed by `auth`. `GET /api/auth/csrf` exists for clients that have no session yet (a public API consumer); the dashboard does **not** call it, because before login there is nothing to protect and after login `/me` already supplies a valid token.

- [ ] **Step 1: Failing tests**

```ts
// src/lib/guard.test.ts
it('routes anonymous users to login except on public pages', () => {
  expect(outcomeToLocation('login', '/devices')).toEqual({ redirect: '/login' });
  expect(outcomeToLocation('login', '/login')).toEqual({});
});

it('routes everyone to setup until it is complete', () => {
  expect(outcomeToLocation('setup', '/login')).toEqual({ redirect: '/setup' });
  expect(outcomeToLocation('setup', '/setup')).toEqual({});
});

it('renders screens for maintenance and offline', () => {
  expect(outcomeToLocation('maintenance', '/devices')).toEqual({ render: 'maintenance' });
  expect(outcomeToLocation('offline', '/setup')).toEqual({ render: 'offline' });
});
```

```ts
// src/lib/stores/auth.test.ts
it('hydrate stores me, csrf and permissions', async () => {
  vi.spyOn(authApi, 'me').mockResolvedValue(me);
  expect(await auth.hydrate()).toBe('ready');
  expect(auth.can('devices.control')).toBe(true);
  expect(auth.can('roles.manage')).toBe(false);
});

it('maps every failure to an outcome', async () => {
  const spy = vi.spyOn(authApi, 'me');
  spy.mockRejectedValueOnce(new ApiError(409, 'setup_required', [], { isSetupRequired: true }));
  expect(await auth.hydrate()).toBe('setup');
  spy.mockRejectedValueOnce(new ApiError(503, 'maintenance', [], { isMaintenance: true }));
  expect(await auth.hydrate()).toBe('maintenance');
  spy.mockRejectedValueOnce(new ApiError(401, 'Tidak terautentikasi'));
  expect(await auth.hydrate()).toBe('login');
  spy.mockRejectedValueOnce(ApiError.offline());
  expect(await auth.hydrate()).toBe('offline');
});

it('401 clears state so admin screens cannot linger', async () => {
  vi.spyOn(authApi, 'me').mockResolvedValueOnce(me);
  await auth.hydrate();
  vi.spyOn(authApi, 'me').mockRejectedValueOnce(new ApiError(401, 'x'));
  await auth.hydrate();
  expect(auth.me).toBeNull();
  expect(auth.can('devices.control')).toBe(false);
});

it('login sets the csrf token from the login response before hydrating', async () => {
  const post = vi.spyOn(authApi, 'login').mockResolvedValue({ authenticated: true, user_id: 1, csrf_token: 'tok-2' });
  vi.spyOn(authApi, 'me').mockResolvedValue({ ...me, csrf_token: 'tok-2' });
  await auth.login('root', 'password-panjang');
  expect(post).toHaveBeenCalled();
  expect(auth.can('devices.control')).toBe(true);
});

it('refresh() replaces permissions without a full reload', async () => {
  vi.spyOn(authApi, 'me').mockResolvedValueOnce(me);
  await auth.hydrate();
  vi.spyOn(authApi, 'me').mockResolvedValueOnce({ ...me, permissions: ['devices.view'] });
  await auth.refresh();
  expect(auth.can('devices.control')).toBe(false);
});
```

- [ ] **Step 2: Verify failure**

- [ ] **Step 3: Implement**

`auth.svelte.ts` uses `authApi.me()` with `silent401: true` so a stale session during hydrate is reported as `'login'`, not by the global handler. `hydrate` sets CSRF from `me.csrf_token`; `while` clearing must also `setCsrfToken(null)`. `refresh()` re-reads `/me` and becomes a no-op when the outcome is not `'ready'`.

`login/+page.svelte` — card; errors under fields from `fieldErrors`; 429 shows "Terlalu banyak percobaan" with the `Retry-After` seconds.

`setup/+page.svelte` — step 1 credentials (confirm field), posts `/api/setup`, sets CSRF, hydrates; step 2 offers "Tambah bot" / "Tambah device" links with a "Lewati" path to `/`.

`+layout.svelte` — hydrate once on mount, apply `guard.outcomeToLocation`, render `offline-screen` / `maintenance-screen` when asked, otherwise `<slot/>`.

- [ ] **Step 4: Verify and commit**

```bash
npm run test -- --run && npm run check
git add -A frontend && git commit -m "feat(fe): auth store, guards, login, setup"
```

---

### Task 4: Application shell, sidebar, two-state connectivity, SSE

**Files:** `src/lib/nav.ts`, `src/lib/components/app-sidebar.svelte`, `maintenance-screen.svelte`, `connection-badge.svelte`, `src/lib/stores/stream.svelte.ts`, `src/lib/stores/connectivity.svelte.ts`, `src/routes/(app)/+layout.svelte`, `src/routes/+layout.svelte`. Tests: `src/lib/nav.test.ts`, `src/lib/stores/stream.test.ts`, `src/lib/stores/connectivity.test.ts`.

**Interfaces:**
- `nav.items` — exactly **12** entries: `/` Overview (`devices.view`), `/devices` (`devices.view`), `/logs/power`, `/logs/activities`, `/logs/errors` (`logs.view`), `/settings` (`settings.view`), `/users` (`users.view`), `/telegram-users` (`telegram_users.view`), `/roles` (`users.view`), `/bots` (`bots.view`), `/backup` (`backup.view`), `/system` (`system.view`).
- `stream`: `devices: Record<number, StreamDevice>` keyed by **id**; `sseConnected: boolean`; `start/stop/reset`. Reconnect backoff `min(30_000, 1000 * 2**attempt)`, **reset to 0 on `onopen`**.
- `connectivity`: `apiOnline: boolean` — set false by the 401/offline path and by any `ApiError.isOffline`; set true by any successful request. Drives the offline screen. **SSE state never sets `apiOnline`.**

- [ ] **Step 1: Failing tests**

```ts
// src/lib/nav.test.ts
it('has exactly 12 unique entries', () => {
  expect(nav.items).toHaveLength(12);
  expect(new Set(nav.items.map((i) => i.href)).size).toBe(12);
});
it('filters by permission', () => {
  expect(nav.visibleItems((p) => p === 'devices.view').map((i) => i.href)).toEqual(['/', '/devices']);
});
```

```ts
// src/lib/stores/stream.test.ts
beforeEach(() => { vi.useFakeTimers(); vi.stubGlobal('EventSource', FakeEventSource); stream.reset(); });
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); FakeEventSource.instances = []; });

it('keys devices by id', () => {
  stream.start();
  FakeEventSource.instances[0].onmessage?.({ data: JSON.stringify({ devices: [{ id: 7, name: 'pompa', online: true }] }) } as MessageEvent);
  expect(stream.devices[7].name).toBe('pompa');
  expect(stream.sseConnected).toBe(true);
});

it('backoff grows, caps, and resets after a successful open', () => {
  stream.start();
  FakeEventSource.instances[0].onerror?.();
  vi.advanceTimersByTime(1000); expect(FakeEventSource.instances).toHaveLength(2);
  FakeEventSource.instances[1].onerror?.();
  vi.advanceTimersByTime(1999); expect(FakeEventSource.instances).toHaveLength(2);
  vi.advanceTimersByTime(1); expect(FakeEventSource.instances).toHaveLength(3);
  FakeEventSource.instances[2].onopen?.();          // success resets the ladder
  FakeEventSource.instances[2].onerror?.();
  vi.advanceTimersByTime(1000); expect(FakeEventSource.instances).toHaveLength(4);
});

it('stop closes the socket and cancels the pending reconnect', () => {
  stream.start();
  FakeEventSource.instances[0].onerror?.();
  stream.stop();
  vi.advanceTimersByTime(120_000);
  expect(FakeEventSource.instances).toHaveLength(1);
  expect(stream.sseConnected).toBe(false);
});

it('an sse failure never marks the api offline', () => {
  connectivity.setApiOnline(true);
  stream.start();
  FakeEventSource.instances[0].onerror?.();
  expect(connectivity.apiOnline).toBe(true);
});
```

```ts
// src/lib/stores/connectivity.test.ts
it('an offline ApiError flips apiOnline false; a success flips it true', () => {
  connectivity.setApiOnline(true);
  connectivity.observe(new ApiError(0, 'x', [], { isOffline: true }));
  expect(connectivity.apiOnline).toBe(false);
  connectivity.observeSuccess();
  expect(connectivity.apiOnline).toBe(true);
});
```

- [ ] **Step 2: Verify failure**

- [ ] **Step 3: Implement**

`stream.svelte.ts` — `EventSource('/api/stream')`; `onopen` sets `sseConnected = true` and `attempt = 0`; `onmessage` rebuilds the id-keyed map; `onerror` closes, sets `sseConnected = false`, schedules `min(30_000, 1000 * 2**attempt++)`; `stop()` clears the timer, closes the source, and sets `sseConnected = false`.

`connectivity.svelte.ts` — `setApiOnline(online)` and `observe(error: ApiError)` / `observeSuccess()`; wired in `client.ts` from Task 2.

Root layout — on `onUnauthorized` from Task 2: `auth.reset(); goto('/login', { replaceState: true })` guarded by a module flag so parallel 401s produce one redirect; the listener is registered once.

`(app)/+layout.svelte` — shadcn sidebar provider; header with breadcrumb, theme toggle, `connection-badge` (two independent dots: "API" and "Realtime"), user dropdown ("Ubah password", "Keluar"); starts/stops the stream on mount/destroy.

- [ ] **Step 4: Verify and commit**

```bash
npm run test -- --run && npm run check
git add -A frontend && git commit -m "feat(fe): shell, sidebar, sse and connectivity states"
```

---

### Task 5: Device management

**Files:** `src/routes/(app)/devices/+page.svelte`, `src/routes/(app)/devices/[id]/+page.svelte`, `src/lib/components/device-card.svelte`, `device-dialog.svelte`, `scan-dialog.svelte`, `dps-editor.svelte`, `confirm-control.svelte`, `src/lib/format.ts`, `src/lib/devices.ts`. Tests: `src/lib/format.test.ts`, `src/lib/devices.test.ts`, `src/lib/scan.test.ts`.

**Interfaces:**
- `format.{watts,volts,amps,age,bytes,dateTime}`
- `devices.{statusText,mergeStream,requiresConfirm,validation}`
- `scan.run(start, poll, {signal, onUpdate, intervalMs = 1500, timeoutMs = 90_000}) -> Promise<ScanCandidate[]>` — aborts via `AbortController`.

- [ ] **Step 1: Failing tests**

```ts
it('formats readings and ages', () => {
  expect(format.watts(12.34)).toBe('12.3 W');
  expect(format.watts(null)).toBe('--');
  expect(format.age(120)).toBe('2 menit lalu');
});
it('explains an unreachable device in Indonesian', () => {
  expect(devices.statusText({ success: false, online: false })).toBe('Perangkat tidak merespons. Periksa IP dan local key.');
});
it('merges stream data by id', () => {
  const merged = devices.mergeStream([base], { 1: { id: 1, online: true, switch_on: true, power_w: 99 } });
  expect(merged[0].live?.power_w).toBe(99);
});
it('confirms control for watchdog devices', () => {
  expect(devices.requiresConfirm({ ...base, features: { watchdog: true } })).toBe(true);
});
it('validates required fields', () => {
  expect(devices.validation({ name: '', tuya_id: '', local_key: '' })).toEqual([
    { key: 'name', message: 'Nama wajib diisi' },
    { key: 'tuya_id', message: 'Tuya ID wajib diisi' },
    { key: 'local_key', message: 'Local key wajib diisi' },
  ]);
});
```

```ts
// src/lib/scan.test.ts
it('stops polling and reports abort when the controller fires', async () => {
  const controller = new AbortController();
  let polls = 0;
  const poll = async () => { polls++; return { status: 'running', candidates: [] }; };
  const promise = scan.run(async () => ({ job_id: 'j', status: 'running' }), poll, {
    signal: controller.signal, intervalMs: 10, timeoutMs: 1000,
  });
  setTimeout(() => controller.abort(), 25);
  await expect(promise).rejects.toMatchObject({ name: 'AbortError' });
  const seen = polls;
  await new Promise((r) => setTimeout(r, 50));
  expect(polls).toBe(seen);   // no polling after abort
});
```

- [ ] **Step 2: Verify failure**

- [ ] **Step 3: Implement**

`devices/+page.svelte` — list merged with stream; controls disabled without `devices.control`; `confirm-control` before toggling a watchdog device; header actions gated by permission; empty state links to the dialog.

`device-dialog.svelte` — full create/edit form; `dps-editor` prefilled from `/api/devices/templates`; features and `access_roles`; client validation then server `fieldErrors`.

`scan-dialog.svelte` — creates an `AbortController`, passes it to `scan.run`, and **aborts on dialog close/unmount**; shows candidates; "Gunakan" prefills the device dialog.

`devices/[id]/+page.svelte` — status, raw DPS table, "Test koneksi" showing `mapped` vs `dps`, edit/delete.

- [ ] **Step 4: Verify and commit**

```bash
npm run test -- --run && npm run check
git add -A frontend && git commit -m "feat(fe): device management, dps editor, cancellable scan"
```

---

### Task 6: Dashboard overview

**Files:** `src/routes/(app)/+page.svelte`, `src/lib/components/stat-tile.svelte`, `power-sparkline.svelte`, `recent-activity.svelte`, `src/lib/overview.ts`. Test: `src/lib/overview.test.ts`.

**Interfaces:**
- `overview.build(input: { stats, health, devices, stream: { devices: Record<number, StreamDevice>; sseConnected: boolean }, activities, powerRows }) -> { tiles, power, activity, alerts }`

`stream` is **one nested object**; `sseConnected` lives inside it. Tiles: `devicesOnline`, `devicesTotal`, `powerNow`, `lastBackup`. `power`: `{ points, current, max }` capped at 120 points. `alerts`: `{level, text}[]` from health ≠ ok, device `last_error`, and `stream.sseConnected === false` (text "Realtime terputus", **not** an offline alert).

- [ ] **Step 1: Failing tests**

```ts
it('builds tiles from stats', () => {
  const model = overview.build({ stats, health: { status: 'ok' }, devices: [], stream: { devices: {}, sseConnected: true }, activities: [] });
  expect(model.tiles.devicesOnline).toBe(2);
  expect(model.tiles.devicesTotal).toBe(3);
  expect(model.tiles.lastBackup).toBe('a.db');
});

it('warns when health is degraded', () => {
  const model = overview.build({ stats, health: { status: 'degraded' }, devices: [], stream: { devices: {}, sseConnected: true }, activities: [] });
  expect(model.alerts.some((a) => a.level === 'warn')).toBe(true);
});

it('warns about realtime without claiming the api is offline', () => {
  const model = overview.build({ stats, health: { status: 'ok' }, devices: [], stream: { devices: {}, sseConnected: false }, activities: [] });
  expect(model.alerts).toContainEqual({ level: 'warn', text: 'Realtime terputus' });
});

it('surfaces the last device error', () => {
  const model = overview.build({ stats, health: { status: 'ok' }, devices: [{ id: 1, label: 'Pompa', last_error: 'Timeout' }], stream: { devices: {}, sseConnected: true }, activities: [] });
  expect(model.alerts).toContainEqual({ level: 'error', text: 'Pompa: Timeout' });
});

it('caps the power series and derives the peak', () => {
  const rows = Array.from({ length: 200 }, (_, i) => ({ power_w: i, created_at: `2026-11-18 10:00:00`, device_id: 1 }));
  const model = overview.build({ stats, health: { status: 'ok' }, devices: [], stream: { devices: {}, sseConnected: true }, activities: [], powerRows: rows });
  expect(model.power.points.length).toBeLessThanOrEqual(120);
  expect(model.power.max).toBe(199);
});
```

- [ ] **Step 2: Verify failure**

- [ ] **Step 3: Implement**

`overview.ts` is pure. Page fetches stats/health/devices/activities/power in `Promise.allSettled`; a rejected tile renders `--` with its own retry, never blanks the page; `ApiError.isOffline` renders the offline screen. Layout: alert strip, four `stat-tile`s, `power-sparkline` (accessible SVG, peak marker), compact device grid, `recent-activity` (8 rows), quick links gated by permission.

- [ ] **Step 4: Verify and commit**

```bash
npm run test -- --run && npm run check
git add -A frontend && git commit -m "feat(fe): dashboard overview"
```

---

### Task 7: Management pages

**Files:** `src/routes/(app)/settings/+page.svelte`, `users/+page.svelte`, `telegram-users/+page.svelte`, `roles/+page.svelte`, `roles/[id]/+page.svelte`, `bots/+page.svelte`, `src/lib/settings-form.ts`, `src/lib/permissions.ts`, `src/lib/components/setting-field.svelte`, `permission-matrix.svelte`, `role-dialog.svelte`, `bot-dialog.svelte`, `password-dialog.svelte`. Tests: `src/lib/settings-form.test.ts`, `src/lib/permissions.test.ts`.

**Interfaces:** `settingsForm.fromSchema(schema, values)` → `{ groups, fields, set, toPayload, validate, setFieldErrors, dirtyKeys }`; `permissions.groupCatalog(payload)`; `permissions.editable(catalog, actorPermissions)`.

**Permission refresh:** after any successful mutation on roles, web users, or telegram users, and whenever a 403 is received, the page calls `auth.refresh()`. This is what makes a revoked permission disappear without a re-login.

- [ ] **Step 1: Failing tests**

```ts
it('groups settings in registry order', () => {
  const form = settingsForm.fromSchema(schema, {});
  expect(form.groups.map((g) => g.name)).toEqual(['Alpha', 'Beta', 'Sistem']);
  expect(form.groups[0].fields.map((f) => f.key)).toEqual(['a.x', 'a.z']);
});
it('sends only changed writable values', () => {
  const form = settingsForm.fromSchema(schema, { 'a.x': 1, 'sys.v': 9 });
  form.set('a.x', 7); form.set('sys.v', 10);
  expect(form.toPayload()).toEqual({ 'a.x': 7 });
});
it('validates ranges', () => {
  const form = settingsForm.fromSchema(schema, { 'a.x': 1 });
  form.set('a.x', 11);
  expect(form.validate()).toEqual([{ key: 'a.x', message: 'Maksimal 10' }]);
});
it('maps server errors without losing edits', () => {
  const form = settingsForm.fromSchema(schema, { 'a.x': 1 });
  form.set('a.x', 5);
  form.setFieldErrors([{ key: 'a.x', message: 'ditolak' }]);
  expect(form.fields.find((f) => f.key === 'a.x')?.error).toBe('ditolak');
  expect(form.toPayload()).toEqual({ 'a.x': 5 });
});
it('labels known permissions and falls back to the key', () => {
  expect(permissions.groupCatalog(catalog)[0].permissions[0].label).toBe('Lihat perangkat');
});
it('offers only permissions the actor holds', () => {
  expect(permissions.editable(catalog, ['devices.view'])).toEqual(['devices.view']);
});
```

- [ ] **Step 2: Verify failure**

- [ ] **Step 3: Implement**

Settings — schema-driven fields (bool→switch, int/float→number, enum→select, string→input, secret→password showing "sudah diisi", json→textarea with parse check), `apply` badge, read-only disabled, sticky save bar, 422 mapped back.

Users — table + create/edit dialog + password reset + deactivate; a 409 "last manager" renders as a blocking explanation on the row. Calls `auth.refresh()` after success.

Telegram users — separate page, numeric id, role limited by `permissions.editable`, note that these accounts cannot log in.

Roles — list and editor with `permission-matrix` (grouped checkboxes, select-all per group, protected keys locked with a tooltip); banner that saving revokes sessions; `auth.refresh()` after save.

Bots — cards with `last_error` (clamped + expand), enable/disable, "Uji", "Ganti token" (write-only, explicit note), delete with typed confirmation.

- [ ] **Step 4: Verify and commit**

```bash
npm run test -- --run && npm run check
git add -A frontend && git commit -m "feat(fe): settings, users, telegram users, roles, bots"
```

---

### Task 8: Monitoring — log pages, audit, system

**Files:** `src/routes/(app)/logs/power/+page.svelte`, `logs/activities/+page.svelte`, `logs/errors/+page.svelte`, `system/+page.svelte`, `src/lib/log-table.ts`, `src/lib/audit.ts`, `src/lib/components/log-table.svelte`, `device-filter.svelte`, `audit-table.svelte`, `health-cards.svelte`. Tests: `src/lib/log-table.test.ts`, `src/lib/audit.test.ts`.

**Interfaces:** `logTable.rows<T>(fetcher, {limit, deviceId})`; `audit.filters(q)` → `URLSearchParams` covering exactly the backend's accepted parameters (`actor_kind, action, result, target_kind, request_id, since, until, limit, offset`).

- [ ] **Step 1: Failing tests**

```ts
it('pages and stops at an empty page', async () => {
  const calls: string[] = [];
  const fetcher = async (p: string) => { calls.push(p); return p.includes('offset=50') ? { items: [], limit: 50, offset: 50 } : { items: [{ id: 1 }], limit: 50, offset: 0 }; };
  const table = logTable.rows(fetcher, { limit: 50 });
  await table.load(); expect(table.items).toHaveLength(1);
  await table.next(); expect(calls[1]).toContain('offset=50'); expect(table.hasNext).toBe(false);
});
it('device filter resets to the first page', async () => {
  const calls: string[] = [];
  const fetcher = async (p: string) => { calls.push(p); return { items: [{ id: 1 }], limit: 50, offset: 0 }; };
  const table = logTable.rows(fetcher, { limit: 50 });
  await table.load(); await table.next(); await table.setDevice(3);
  expect(calls.at(-1)).toContain('offset=0');
  expect(calls.at(-1)).toContain('device_id=3');
});
it('audit filters omit empty values and encode', () => {
  expect(audit.filters({ result: 'denied', action: 'access.denied', actor_kind: '', limit: 50 }).toString())
    .toBe('action=access.denied&result=denied&limit=50');
});
```

- [ ] **Step 2: Verify failure**

- [ ] **Step 3: Implement**

Three log pages share `log-table`; `device-filter` from `/api/devices`; empty states; 50-row pages; power page adds the sparkline. Error traces render in `<pre>` via `textContent` — never `{@html}`.

`system/+page.svelte` — health cards, stats block, maintenance toggle (reason + auto-off, confirmation), `audit-table` with filters and a JSON details drawer; the audit section hides without `audit.view`.

- [ ] **Step 4: Verify and commit**

```bash
npm run test -- --run && npm run check
git add -A frontend && git commit -m "feat(fe): log pages, audit table, system health"
```

---

### Task 9: Backup UI, static build, external nginx, CI, integration tests

**Decision:** no frontend container and no nginx inside this repo. The dashboard is a
static build deployed to the operator's existing nginx, which already terminates TLS and
acts as the outer wall. This removes a container, a port and a config file from the repo.

**Files:** `src/routes/(app)/backup/+page.svelte`, `src/lib/backup-form.ts`, `src/lib/components/restore-dialog.svelte`, `.github/workflows/frontend.yml`, `frontend/README.md`, `docs/deploy/nginx-example.conf` (reference, not shipped), `src/lib/api/integration.test.ts`. Tests: `src/lib/backup-form.test.ts`, `src/lib/api/integration.test.ts`.

**Interfaces:** `backupForm.restore()` → `{ valid, setPassword, setConfirm, setFile, toFormData }`. Integration tests run through the Vite dev proxy so cookies are same-origin.

- [ ] **Step 1: Failing tests**

```ts
it('requires password and the literal RESTORE', () => {
  const form = backupForm.restore();
  expect(form.valid).toBe(false);
  form.setPassword('rahasia'); form.setConfirm('bukan'); expect(form.valid).toBe(false);
  form.setConfirm('restore'); expect(form.valid).toBe(true);
  expect(form.toFormData().get('confirm')).toBe('RESTORE');
});

it('refuses a file over 200 MB', () => {
  expect(backupForm.restore().setFile(new File([new Uint8Array(201 * 1024 * 1024)], 'big.db')))
    .toBe('Ukuran file maksimal 200 MB');
});
```

```ts
// src/lib/api/integration.test.ts — opt-in, through the dev proxy (same origin)
const enabled = process.env.VITE_TEST_API === '1';

describe.skipIf(!enabled)('backend integration via dev proxy', () => {
  it('setup status is public', async () => {
    const status = await api<{ required: boolean }>('/api/setup/status');
    expect(typeof status.required).toBe('boolean');
  });

  it('protected routes answer 401 without a session', async () => {
    await expect(api('/api/settings')).rejects.toMatchObject({ status: 401 });
  });

  it('sessions and CSRF work end to end', async () => {
    const login = await api<{ csrf_token: string }>('/api/auth/login', {
      method: 'POST', body: { username: 'root', password: 'password-panjang' },
    });
    setCsrfToken(login.csrf_token);
    await expect(api('/api/auth/me')).resolves.toMatchObject({ username: 'root' });
    setCsrfToken(null);
    await expect(api('/api/settings', { method: 'PATCH', body: { values: { 'ui.title': 'X' } } }))
      .rejects.toMatchObject({ status: 403 });
  });
});
```

`credentials: 'same-origin'` only sends cookies to the page's own origin, which is why the
test targets the dev server (`http://localhost:5173`) rather than `127.0.0.1:8080`.

- [ ] **Step 2: Verify failure**

- [ ] **Step 3: Backup UI**

Table (filename, kind badge, size, created_at), "Buat backup" (`backup.create`), download
(`backup.restore`, warning that it contains secrets), restore dialog with file + password +
typed `RESTORE`, warnings about maintenance and session revocation. On 422 with `stage`,
render `upload|integrity|schema|version|swap` in Indonesian and state that maintenance stays on.

- [ ] **Step 4: CI workflow**

`.github/workflows/frontend.yml` — `working-directory: frontend`; `npm ci`, `npm run check`,
`npm run test -- --run`, `npm run build`; upload `frontend/build` as an artifact so the
operator can download the deployed bundle instead of building on the server.

- [ ] **Step 5: Reference nginx config (documentation, not shipped)**

`docs/deploy/nginx-example.conf` is a template for the operator's existing nginx. The three
lines that must be right:

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $http_host;          # NOT $host — it drops the port and breaks Origin checks
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off;                       # SSE
    proxy_read_timeout 1h;
}
location / { try_files $uri /index.html; }
```

`frontend/README.md` documents: `npm run build` output, where to copy `build/`, the nginx
snippet, `FORWARDED_ALLOW_IPS` on the backend, and `security.cookie_secure=true` when TLS is on.

- [ ] **Step 6: Verify**

```bash
cd frontend && npm run test -- --run && npm run check && npm run build
cd .. && git add -A && git commit -m "feat(fe): backup ui, static build, external nginx docs, ci"
```

- [ ] **Step 7: End-to-end smoke (manual, backend must run)**

```bash
# terminal 1
cd backend && PYTHONPATH=src python -m tuyabot.main
# terminal 2
cd frontend && npm run dev
```

Expected: `/setup` → overview → create device → toggle (SSE updates the card) → settings save →
role edit → backup row → system health. Stop the backend: pages show the offline screen.
Restart it: retry recovers.

- [ ] **Step 8: Verify through the operator's nginx**

After copying `build/` and applying the snippet:

```bash
curl -s https://tuya.example.com/ | head -c 80                  # index.html
curl -s https://tuya.example.com/api/setup/status               # proxied JSON
curl -s -o /dev/null -w '%{http_code}
' -X POST https://tuya.example.com/api/auth/login   -H 'Content-Type: application/json' -d '{"username":"root","password":"password-panjang"}'
```

Expected: HTML, JSON, and **not 403**. A 403 means nginx sends `$host` instead of `$http_host`.
Then confirm in `GET /api/audit` that the login row records the real client IP, not the proxy's —
if it shows the proxy IP, `FORWARDED_ALLOW_IPS` on the backend does not include the proxy.

---

## Self-Review Notes

- Contract block now covers every mutation Task 7 needs (web users, telegram users, bots, roles, backup restore) with bodies, permissions, and error shapes, verified from source.
- Central 401 lives in Task 2 and covers GET; login/setup/csrf are excluded by path and `silent401` covers hydrate.
- `cn` dependencies are installed explicitly.
- The `try/catch` in `client.ts` wraps only `fetch`, and a malformed JSON body is tested to return `undefined`, not offline.
- `/api/auth/csrf` is documented as unused by the dashboard, with the reason.
- SSE resets backoff on `onopen`, `stop()` cancels the timer (tested), and SSE failure never flips the API state (tested).
- Scan polling aborts on dialog close (tested).
- `overview.build` takes a nested `stream: { devices, sseConnected }`, and tests use that shape.
- Audit query parameters match the backend's accepted names exactly.
- Integration tests run through the dev proxy so cookies are genuinely same-origin.
- Deployment: static build served by the operator's existing nginx; no frontend container, no nginx config shipped as code. `Host $http_host` is documented with the failure it prevents, and the smoke step checks both the proxy pass-through and the recorded client IP.
- API layer is split by domain; `client.ts` holds transport only.

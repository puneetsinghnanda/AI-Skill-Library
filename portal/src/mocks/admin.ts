/**
 * MSW handlers for the admin API (SDD-13 §7.2): tests and `npm run demo` only, never in a
 * production build. They mirror the checks of services/insights/app/api/v1/admin.py and the admin
 * branch of `POST /v1/keys/{key_id}/revoke`, against an in-memory store of invented data, so the
 * screens meet the same 400/401/403/404 answers as with the real service. Nothing is persisted:
 * the store resets with `resetScenario()` and on every page load of the demo.
 */
import { http, HttpResponse, type JsonBodyType, type PathParams } from 'msw';
import { SKILLS, USERS, type DemoUser, type DemoUserId } from './fixtures';

type ConsentScope = 'code_processing' | 'companion_storage' | 'product_prs' | 'ci_webhook';

interface MockClient {
  code: string;
  consentRef: string | null;
  scope: ConsentScope[];
  recordedAt: string | null;
  withdrawnAt: string | null;
}
interface MockUser {
  pseudonym: string;
  appRoles: string[];
  active: boolean;
}
interface MockGrant {
  id: string;
  user: string;
  role: string;
  scopeType: string;
  scope: string | null;
  grantedAt: string;
  grantedBy: string | null;
  revokedAt: string | null;
}
interface MockKey {
  keyId: string;
  user: string;
  deviceLabel: string | null;
  createdAt: string;
  expiresAt: string;
  revokedAt: string | null;
  reason: string | null;
}

interface Store {
  clients: MockClient[];
  projects: { code: string; client: string }[];
  systems: { code: string; project: string; domain: string; repos: string[] }[];
  users: MockUser[];
  grants: MockGrant[];
  keys: MockKey[];
  denylistVersion: number;
  audit: { action: string; target: string }[];
  seq: number;
}

const T0 = '2026-01-12T09:30:00Z';
const T_OLD = '2025-06-02T08:00:00Z';
const T_END = '2030-01-12T09:30:00Z';
const ADMIN = 'eng-5d3e';

function seed(): Store {
  return {
    clients: [
      {
        code: 'CL-DEMO',
        consentRef: 'CONSENT-0001',
        scope: ['code_processing', 'companion_storage', 'product_prs'],
        recordedAt: T0,
        withdrawnAt: null,
      },
      { code: 'CL-SAMPLE', consentRef: null, scope: [], recordedAt: null, withdrawnAt: null },
    ],
    projects: [
      { code: 'PRJ-07', client: 'CL-DEMO' },
      { code: 'PRJ-09', client: 'CL-DEMO' },
    ],
    systems: [
      { code: 'SYS-ORD', project: 'PRJ-07', domain: 'digital', repos: ['order-service'] },
      { code: 'SYS-TKT', project: 'PRJ-07', domain: 'digital', repos: ['ticket-api'] },
      { code: 'SYS-INV', project: 'PRJ-09', domain: 'embedded', repos: ['inventory-firmware'] },
    ],
    users: [
      { pseudonym: 'eng-4f2a', appRoles: ['Engineer', 'TechLead'], active: true },
      { pseudonym: 'eng-7a1c', appRoles: ['Engineer', 'TechLead'], active: true },
      { pseudonym: 'eng-91c0', appRoles: ['Engineer'], active: true },
      { pseudonym: 'eng-77de', appRoles: ['Engineer'], active: true },
      { pseudonym: 'eng-0b3e', appRoles: ['Engineer'], active: true },
      { pseudonym: 'eng-2c4b', appRoles: ['Business'], active: true },
      { pseudonym: 'eng-5d3e', appRoles: ['Admin'], active: true },
    ],
    grants: [
      grant('6b0f2a7e-1c4d-4e8a-9b21-0d5c3e7f9a01', 'eng-91c0', 'engineer', 'system', 'SYS-TKT'),
      grant('6b0f2a7e-1c4d-4e8a-9b21-0d5c3e7f9a02', 'eng-77de', 'engineer', 'system', 'SYS-ORD'),
      grant('6b0f2a7e-1c4d-4e8a-9b21-0d5c3e7f9a03', 'eng-7a1c', 'tech_lead', 'system', 'SYS-ORD'),
      grant('6b0f2a7e-1c4d-4e8a-9b21-0d5c3e7f9a04', 'eng-4f2a', 'engineer', 'system', 'SYS-ORD'),
      grant('6b0f2a7e-1c4d-4e8a-9b21-0d5c3e7f9a05', 'eng-2c4b', 'viewer', 'org', null),
      grant('6b0f2a7e-1c4d-4e8a-9b21-0d5c3e7f9a06', ADMIN, 'admin', 'org', null, null),
      {
        ...grant(
          '6b0f2a7e-1c4d-4e8a-9b21-0d5c3e7f9a07',
          'eng-0b3e',
          'engineer',
          'system',
          'SYS-TKT',
        ),
        grantedAt: T_OLD,
        revokedAt: T0,
      },
    ],
    keys: [
      key('key_01J9ZK2M4Q8X7T3B5N6R0VWY01', 'eng-91c0', 'laptop-a'),
      key('key_01J9ZK2M4Q8X7T3B5N6R0VWY02', 'eng-77de', 'laptop-b'),
      {
        ...key('key_01J9ZK2M4Q8X7T3B5N6R0VWY03', 'eng-77de', 'old-laptop'),
        createdAt: T_OLD,
        revokedAt: T0,
        reason: 'replaced',
      },
      {
        ...key('key_01J9ZK2M4Q8X7T3B5N6R0VWY04', 'eng-4f2a', 'desk-pc'),
        createdAt: T_OLD,
        expiresAt: T0,
      },
      key('key_01J9ZK2M4Q8X7T3B5N6R0VWY05', 'eng-4f2a', 'laptop-c'),
    ],
    denylistVersion: 3,
    audit: [],
    seq: 2,
  };
}

function grant(
  id: string,
  user: string,
  role: string,
  scopeType: string,
  scope: string | null,
  grantedBy: string | null = ADMIN,
): MockGrant {
  return { id, user, role, scopeType, scope, grantedAt: T0, grantedBy, revokedAt: null };
}

function key(keyId: string, user: string, deviceLabel: string): MockKey {
  return {
    keyId,
    user,
    deviceLabel,
    createdAt: T0,
    expiresAt: T_END,
    revokedAt: null,
    reason: null,
  };
}

let store = seed();

export function resetAdminStore(): void {
  store = seed();
}

/** Audit actions the mock recorded, for tests (the server writes `audit_log`). */
export function adminAudit(): { action: string; target: string }[] {
  return [...store.audit];
}

/* ------------------------------------------------------------------ helpers */
const CEILING: Record<string, string[] | 'any'> = {
  viewer: 'any',
  engineer: ['Engineer', 'TechLead'],
  tech_lead: ['TechLead'],
  skill_owner: ['Engineer', 'TechLead'],
  stage_approver: ['TechLead'],
  eng_lead: ['TechLead', 'Admin'],
  admin: ['Admin'],
};
const ROLE_SCOPES: Record<string, string[]> = {
  viewer: ['org'],
  engineer: ['system'],
  tech_lead: ['system'],
  skill_owner: ['skill'],
  stage_approver: ['stage'],
  eng_lead: ['org', 'client', 'project'],
  admin: ['org'],
};
const CONSENT_SCOPES = ['code_processing', 'companion_storage', 'product_prs', 'ci_webhook'];
const ADMIN_REASONS = ['user_request', 'offboarded', 'admin_other', 'lost_device', 'compromised'];

class Fail extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    detail: string,
  ) {
    super(detail);
  }
}

function problem(status: number, code: string, detail: string, request: Request) {
  return HttpResponse.json(
    {
      type: `/errors/${code}`,
      title: detail,
      status,
      code,
      detail,
      request_id: request.headers.get('x-request-id') ?? 'unknown',
    },
    { status, headers: { 'Content-Type': 'application/problem+json' } },
  );
}

const bad = (field: string, msg = 'String should match pattern') =>
  new Fail(400, 'E-API-01', `body.${field}: ${msg}`);

function str(body: Record<string, unknown>, field: string, re?: RegExp, max = 200): string {
  const v = body[field];
  if (typeof v !== 'string' || v.length === 0 || v.length > max) throw bad(field, 'Field required');
  if (re && !re.test(v)) throw bad(field);
  return v;
}

function only(body: Record<string, unknown>, fields: string[]) {
  const extra = Object.keys(body).find((k) => !fields.includes(k));
  if (extra) throw bad(extra, 'Extra inputs are not permitted');
}

function now(): string {
  return new Date().toISOString();
}

function uuid(): string {
  store.seq += 1;
  return `6b0f2a7e-1c4d-4e8a-9b21-${store.seq.toString(16).padStart(12, '0')}`;
}

/** Fixture write token: `tm-fixture.<user>.write`. A read token is refused like the server does. */
function writer(request: Request): DemoUser {
  const h = request.headers.get('authorization') ?? '';
  const m = /^Bearer tm-fixture\.(viewer|engineer|lead|admin)(\.write)?$/.exec(h);
  if (!m) throw new Fail(401, 'E-ING-07', 'Missing bearer token');
  if (!m[2]) throw new Fail(401, 'E-ING-07', 'Token scope does not allow this route');
  return USERS[m[1] as DemoUserId];
}

function adminOf(request: Request): DemoUser {
  const u = writer(request);
  if (!u.me.roles.some((r) => r.role === 'admin')) throw new Fail(403, 'E-API-03', 'Admin only');
  return u;
}

type Handler = (args: { body: Record<string, unknown>; params: PathParams; request: Request }) => {
  status?: number;
  json: JsonBodyType;
};

function post(path: string, fn: Handler) {
  return http.post(path, async ({ request, params }) => {
    try {
      let body: unknown;
      try {
        body = await request.json();
      } catch {
        throw new Fail(400, 'E-API-01', 'body: JSON decode error');
      }
      if (typeof body !== 'object' || body === null || Array.isArray(body))
        throw new Fail(400, 'E-API-01', 'body: Input should be a valid dictionary');
      const out = fn({ body: body as Record<string, unknown>, params, request });
      return HttpResponse.json(out.json, { status: out.status ?? 200 });
    } catch (e) {
      if (e instanceof Fail) return problem(e.status, e.code, e.message, request);
      throw e;
    }
  });
}

/** Lists take the Portal.Read fixture token, like the server (`tm-fixture.<user>`, no `.write`). */
function adminReader(request: Request): DemoUser {
  const h = request.headers.get('authorization') ?? '';
  const m = /^Bearer tm-fixture\.(viewer|engineer|lead|admin)$/.exec(h);
  if (!m) throw new Fail(401, 'E-API-02', 'Token scope does not allow this route');
  const u = USERS[m[1] as DemoUserId];
  if (!u.me.roles.some((r) => r.role === 'admin')) throw new Fail(403, 'E-API-03', 'Admin only');
  return u;
}

/** Offset cursor over a sorted array (the server's cursor is a keyset; both are opaque). */
function paginate<T>(items: T[], url: URL) {
  const limit = Number(url.searchParams.get('limit') ?? 25);
  if (!Number.isInteger(limit) || limit < 1 || limit > 100)
    throw new Fail(400, 'E-API-01', 'limit must be 1-100');
  const cursor = url.searchParams.get('cursor');
  const start = cursor ? Number(atob(cursor)) : 0;
  if (!Number.isInteger(start) || start < 0) throw new Fail(400, 'E-API-01', 'Invalid cursor');
  const page = items.slice(start, start + limit);
  const next = start + limit < items.length ? btoa(String(start + limit)) : null;
  return {
    data: { items: page },
    meta: { generated_at: now(), scope: { level: 'org' } },
    page: { limit, next_cursor: next },
  };
}

function oneOf(url: URL, name: string, allowed: string[]): string | null {
  const v = url.searchParams.get(name);
  if (v !== null && !allowed.includes(v)) throw bad(name, `Input should be ${allowed.join(', ')}`);
  return v;
}

function get(path: string, fn: (args: { url: URL; params: PathParams }) => JsonBodyType) {
  return http.get(path, ({ request, params }) => {
    try {
      adminReader(request);
      return HttpResponse.json(fn({ url: new URL(request.url), params }), {
        headers: { 'Cache-Control': 'no-store' },
      });
    } catch (e) {
      if (e instanceof Fail) return problem(e.status, e.code, e.message, request);
      throw e;
    }
  });
}

function consentStatus(c: MockClient): 'recorded' | 'withdrawn' | 'none' {
  if (c.withdrawnAt) return 'withdrawn';
  return c.recordedAt ? 'recorded' : 'none';
}

function keyStatus(k: MockKey): 'active' | 'revoked' | 'expired' {
  if (k.revokedAt) return 'revoked';
  return k.expiresAt <= now() ? 'expired' : 'active';
}

const byCode = <T extends { code: string }>(a: T, b: T) => a.code.localeCompare(b.code);

/* ------------------------------------------------------------------ routes */
export const adminHandlers = [
  get('/v1/admin/clients', ({ url }) => {
    const consent = oneOf(url, 'consent', ['recorded', 'withdrawn', 'none']);
    const rows = [...store.clients]
      .sort(byCode)
      .filter((c) => !consent || consentStatus(c) === consent)
      .map((c) => ({
        code: c.code,
        consent: {
          status: consentStatus(c),
          ref: c.consentRef,
          scope: c.scope,
          recorded_at: c.recordedAt,
          withdrawn_at: c.withdrawnAt,
        },
        projects: store.projects.filter((p) => p.client === c.code).length,
        created_at: T0,
      }));
    return paginate(rows, url);
  }),

  get('/v1/admin/projects', ({ url }) => {
    const client = url.searchParams.get('client');
    const rows = [...store.projects]
      .sort(byCode)
      .filter((p) => !client || p.client === client)
      .map((p) => ({
        code: p.code,
        client: p.client,
        systems: store.systems.filter((s) => s.project === p.code).length,
      }));
    return paginate(rows, url);
  }),

  get('/v1/admin/systems', ({ url }) => {
    const client = url.searchParams.get('client');
    const project = url.searchParams.get('project');
    const clientOf = (p: string) => store.projects.find((x) => x.code === p)?.client ?? '';
    const rows = [...store.systems]
      .sort(byCode)
      .filter(
        (s) => (!project || s.project === project) && (!client || clientOf(s.project) === client),
      )
      .map((s) => ({
        code: s.code,
        project: s.project,
        client: clientOf(s.project),
        domain: s.domain,
        companion_repo: `example-org/${s.code.toLowerCase()}-companion`,
        lifecycle_state: 'PROVISIONED',
        product_repos: s.repos.map((name) => ({
          name,
          github_full_name: `example-org/${name}`,
          kind: 'product',
        })),
        created_at: T0,
      }));
    return paginate(rows, url);
  }),

  get('/v1/admin/role-grants', ({ url }) => {
    const status = oneOf(url, 'status', ['active', 'revoked', 'all']) ?? 'all';
    const user = url.searchParams.get('user');
    const role = url.searchParams.get('role');
    const rows = [...store.grants]
      .sort((a, b) => b.grantedAt.localeCompare(a.grantedAt) || b.id.localeCompare(a.id))
      .filter(
        (g) =>
          (status === 'all' || (status === 'active') === !g.revokedAt) &&
          (!user || g.user === user) &&
          (!role || g.role === role),
      )
      .map((g) => ({
        id: g.id,
        user: g.user,
        role: g.role,
        scope_type: g.scopeType,
        scope: g.scope,
        status: g.revokedAt ? 'revoked' : 'active',
        granted_at: g.grantedAt,
        granted_by: g.grantedBy,
        revoked_at: g.revokedAt,
      }));
    return paginate(rows, url);
  }),

  get('/v1/admin/users', ({ url }) => {
    const active = oneOf(url, 'active', ['true', 'false']);
    const role = url.searchParams.get('role');
    const rolesOf = (p: string) =>
      [
        ...new Set(store.grants.filter((g) => g.user === p && !g.revokedAt).map((g) => g.role)),
      ].sort();
    const rows = [...store.users]
      .sort((a, b) => a.pseudonym.localeCompare(b.pseudonym))
      .filter((u) => active === null || String(u.active) === active)
      .filter((u) => !role || rolesOf(u.pseudonym).includes(role))
      .map((u) => ({
        pseudonym: u.pseudonym,
        app_roles: [...u.appRoles].sort(),
        roles: rolesOf(u.pseudonym),
        active: u.active,
        erased: false,
        created_at: T0,
        // The mock never reveals names: the admin screens do not ask for them (RD-1).
        display_name: null,
      }));
    return paginate(rows, url);
  }),

  get('/v1/admin/users/:pseudonym/keys', ({ url, params }) => {
    const pseudonym = String(params.pseudonym);
    if (!/^eng-[0-9a-f]{4,8}$/.test(pseudonym))
      throw new Fail(400, 'E-API-01', 'path.pseudonym: String should match pattern');
    if (!store.users.some((u) => u.pseudonym === pseudonym))
      throw new Fail(404, 'E-API-04', 'User not found');
    const status = oneOf(url, 'status', ['active', 'revoked', 'expired', 'all']) ?? 'all';
    const rows = store.keys
      .filter((k) => k.user === pseudonym && (status === 'all' || keyStatus(k) === status))
      .sort((a, b) => b.createdAt.localeCompare(a.createdAt) || b.keyId.localeCompare(a.keyId))
      .map((k) => ({
        key_id: k.keyId,
        device_label: k.deviceLabel,
        status: keyStatus(k),
        created_at: k.createdAt,
        expires_at: k.expiresAt,
        revoked_at: k.revokedAt,
        revoked_reason: k.reason,
      }));
    return {
      ...paginate(rows, url),
      meta: { generated_at: now(), scope: { level: 'org' }, user: pseudonym },
    };
  }),

  post('/v1/admin/clients', ({ body, request }) => {
    adminOf(request);
    only(body, ['code', 'display_name', 'aliases']);
    const code = str(body, 'code', /^CL-[0-9A-Z]{2,8}$/);
    str(body, 'display_name');
    if (store.clients.some((c) => c.code === code))
      throw new Fail(400, 'E-API-01', 'Client code already exists');
    store.clients.push({
      code,
      consentRef: null,
      scope: [],
      recordedAt: null,
      withdrawnAt: null,
    });
    store.denylistVersion += 1;
    store.audit.push(
      { action: 'client_create', target: code },
      { action: 'denylist_change', target: String(store.denylistVersion) },
    );
    return {
      status: 201,
      json: { id: uuid(), code, denylist_version: store.denylistVersion },
    };
  }),

  post('/v1/admin/clients/:code/consent', ({ body, params, request }) => {
    adminOf(request);
    only(body, ['action', 'consent_ref', 'scope']);
    const code = String(params.code);
    const client = store.clients.find((c) => c.code === code);
    if (!client) throw new Fail(404, 'E-API-04', 'Client not found');
    const action = body.action ?? 'record';
    if (action === 'record') {
      const ref = body.consent_ref;
      const scope = Array.isArray(body.scope) ? (body.scope as string[]) : [];
      if (typeof ref === 'string' && !/^[A-Z0-9-]{3,40}$/.test(ref)) throw bad('consent_ref');
      if (scope.some((s) => !CONSENT_SCOPES.includes(s)))
        throw bad('scope', 'Input should be one of the consent scopes');
      if (!ref || scope.length === 0)
        throw new Fail(400, 'E-API-01', 'consent_ref and scope are required');
      client.consentRef = ref as string;
      client.scope = [...new Set(scope)].sort() as ConsentScope[];
      client.recordedAt = now();
      client.withdrawnAt = null;
      store.audit.push({ action: 'consent_record', target: code });
    } else if (action === 'withdraw') {
      client.withdrawnAt = now();
      store.audit.push({ action: 'consent_withdraw', target: code });
    } else {
      throw bad('action', "Input should be 'record' or 'withdraw'");
    }
    return {
      json: { code, recorded_at: client.recordedAt, withdrawn_at: client.withdrawnAt },
    };
  }),

  post('/v1/admin/projects', ({ body, request }) => {
    adminOf(request);
    only(body, ['client', 'code']);
    const client = str(body, 'client', /^CL-[0-9A-Z]{2,8}$/);
    const code = str(body, 'code', /^PRJ-[0-9A-Z]{2,8}$/);
    if (!store.clients.some((c) => c.code === client))
      throw new Fail(404, 'E-API-04', 'Client not found');
    if (store.projects.some((p) => p.code === code))
      throw new Fail(400, 'E-API-01', 'Project code already exists');
    store.projects.push({ code, client });
    store.audit.push({ action: 'project_create', target: code });
    return { status: 201, json: { id: uuid(), code, client } };
  }),

  post('/v1/admin/systems', ({ body, request }) => {
    adminOf(request);
    only(body, ['project', 'code', 'domain', 'companion_repo', 'product_repos']);
    const project = str(body, 'project', /^PRJ-[0-9A-Z]{2,8}$/);
    const code = str(body, 'code', /^SYS-[0-9A-Z]{2,8}$/);
    const domain = str(body, 'domain', /^[a-z][a-z0-9-]{1,30}$/);
    str(body, 'companion_repo', /^[A-Za-z0-9_.-]{1,100}\/[A-Za-z0-9_.-]{1,100}$/, 201);
    const repos = Array.isArray(body.product_repos)
      ? (body.product_repos as Record<string, unknown>[])
      : [];
    const names = repos.map((r, i) => {
      if (!/^[a-z0-9][a-z0-9-]{0,60}$/.test(String(r.name ?? '')))
        throw bad(`product_repos.${i}.name`);
      if (!/^[A-Za-z0-9_.-]{1,100}\/[A-Za-z0-9_.-]{1,100}$/.test(String(r.github_full_name ?? '')))
        throw bad(`product_repos.${i}.github_full_name`);
      return String(r.name);
    });
    if (!store.projects.some((p) => p.code === project))
      throw new Fail(404, 'E-API-04', 'Project not found');
    if (store.systems.some((s) => s.code === code))
      throw new Fail(400, 'E-API-01', 'System code or repo already exists');
    store.systems.push({ code, project, domain, repos: names });
    store.audit.push({ action: 'system_create', target: code });
    return { status: 201, json: { id: uuid(), code, project } };
  }),

  post('/v1/admin/role-grants', ({ body, request }) => {
    const me = adminOf(request);
    only(body, ['user', 'role', 'scope_type', 'scope']);
    const user = str(body, 'user', /^eng-[0-9a-f]{4,8}$/);
    const role = str(body, 'role');
    const scopeType = str(body, 'scope_type');
    const scope = typeof body.scope === 'string' && body.scope ? body.scope : null;
    if (!(role in ROLE_SCOPES)) throw bad('role', 'Input should be a known role');
    if (!ROLE_SCOPES[role]?.includes(scopeType))
      throw new Fail(400, 'E-API-01', `${role} cannot be granted at ${scopeType} scope`);
    const u = store.users.find((x) => x.pseudonym === user);
    if (!u || !u.active) throw new Fail(404, 'E-API-04', 'User not found');
    if (u.pseudonym === me.me.pseudonym)
      throw new Fail(403, 'E-ADM-01', 'An admin cannot grant a role to themselves');
    const ceiling = CEILING[role];
    if (ceiling !== 'any' && !ceiling?.some((r) => u.appRoles.includes(r)))
      throw new Fail(
        400,
        'E-API-01',
        `The user's app roles do not allow ${role} (needs ${JSON.stringify(ceiling)})`,
      );
    if (scopeType !== 'org') {
      if (!scope) throw new Fail(400, 'E-API-01', 'scope is required');
      const found =
        (scopeType === 'client' && store.clients.some((c) => c.code === scope)) ||
        (scopeType === 'project' && store.projects.some((p) => p.code === scope)) ||
        (scopeType === 'system' && store.systems.some((s) => s.code === scope)) ||
        (scopeType === 'skill' && SKILLS.some((s) => s.id === scope)) ||
        (scopeType === 'stage' &&
          ['requirements', 'design', 'build', 'test', 'operate'].includes(scope));
      if (!found) throw new Fail(404, 'E-API-04', 'Scope not found');
    }
    if (
      store.grants.some(
        (g) =>
          !g.revokedAt &&
          g.user === user &&
          g.role === role &&
          g.scopeType === scopeType &&
          g.scope === (scopeType === 'org' ? null : scope),
      )
    )
      throw new Fail(400, 'E-API-01', 'The grant already exists');
    const id = uuid();
    store.grants.push({
      id,
      user,
      role,
      scopeType,
      scope: scopeType === 'org' ? null : scope,
      grantedAt: now(),
      grantedBy: me.me.pseudonym,
      revokedAt: null,
    });
    store.audit.push({ action: 'role_grant', target: id });
    return {
      status: 201,
      json: { id, user, role, scope_type: scopeType, scope: body.scope ?? null },
    };
  }),

  post('/v1/admin/role-grants/:grantId/revoke', ({ body, params, request }) => {
    adminOf(request);
    only(body, ['reason']);
    str(body, 'reason');
    const id = String(params.grantId);
    if (!/^[0-9a-f-]{36}$/.test(id))
      throw new Fail(400, 'E-API-01', 'path.grant_id: String should match pattern');
    const g = store.grants.find((x) => x.id === id && !x.revokedAt);
    if (!g) throw new Fail(404, 'E-API-04', 'Active grant not found');
    g.revokedAt = now();
    store.audit.push({ action: 'role_revoke', target: id });
    return { json: { id, revoked_at: g.revokedAt } };
  }),

  post('/v1/admin/users/:pseudonym/deactivate', ({ body, params, request }) => {
    adminOf(request);
    only(body, ['reason']);
    str(body, 'reason');
    const pseudonym = String(params.pseudonym);
    if (!/^eng-[0-9a-f]{4,8}$/.test(pseudonym))
      throw new Fail(400, 'E-API-01', 'path.pseudonym: String should match pattern');
    const u = store.users.find((x) => x.pseudonym === pseudonym);
    if (!u) throw new Fail(404, 'E-API-04', 'User not found');
    u.active = false;
    const t = now();
    const keys = store.keys.filter((k) => k.user === pseudonym && !k.revokedAt);
    for (const k of keys) {
      k.revokedAt = t;
      k.reason = 'offboarded';
      store.audit.push({ action: 'key_revoke', target: k.keyId });
    }
    const grants = store.grants.filter((g) => g.user === pseudonym && !g.revokedAt);
    for (const g of grants) g.revokedAt = t;
    store.audit.push({ action: 'user_deactivate', target: pseudonym });
    return {
      json: {
        pseudonym,
        active: false,
        keys_revoked: keys.map((k) => k.keyId),
        grants_revoked: grants.length,
      },
    };
  }),

  post('/v1/keys/:keyId/revoke', ({ body, params, request }) => {
    const u = writer(request);
    only(body, ['reason', 'compromised_since', 'note']);
    const reason = str(body, 'reason');
    const keyId = String(params.keyId);
    const isAdmin = u.me.roles.some((r) => r.role === 'admin');
    const key = store.keys.find((k) => k.keyId === keyId);
    if (!key || (key.user !== u.me.pseudonym && !isAdmin))
      throw new Fail(404, 'E-KEY-04', 'Key not found');
    if (!ADMIN_REASONS.includes(reason))
      throw new Fail(403, 'E-AUTH-08', `Reason ${reason} is not allowed for this caller`);
    key.revokedAt = key.revokedAt ?? now();
    key.reason = reason;
    store.audit.push({ action: 'key_revoke', target: keyId });
    return {
      json: {
        key_id: keyId,
        revoked_at: key.revokedAt,
        revoked_reason: reason,
        compromised_since:
          reason === 'lost_device' || reason === 'compromised'
            ? (typeof body.compromised_since === 'string' && body.compromised_since) || T0
            : null,
      },
    };
  }),
];

/**
 * MSW handlers for the read API: tests and `npm run demo` only, never in a production build.
 * They mimic the server's role filtering (SDD-09 §5.2-§5.4) from the fixture token, so the
 * role-visibility tests exercise the same 403/404 paths the real service returns.
 */
import { http, HttpResponse, type PathParams } from 'msw';
import type { Meta, Page } from '../api/types';
import {
  ENG_SKILLS,
  ENG_USAGE,
  POD_METRICS,
  POD_ROWS,
  RELEASES,
  ROLES,
  RUN_ROWS,
  SKILLS,
  SYSTEMS,
  USERS,
  businessFor,
  capabilityMap,
  engHealth,
  engRuns,
  homeFor,
  improvementReport,
  onePagerMarkdown,
  podCard,
  podDetail,
  runDetail,
  runItem,
  skillDetail,
  statusData,
  type DemoUser,
  type DemoUserId,
  PHASES,
} from './fixtures';
import { adminHandlers, resetAdminStore } from './admin';

/** Switches for tests and the demo banner. */
export const scenario = {
  behind: false,
  empty: false,
};

export function resetScenario(): void {
  scenario.behind = false;
  scenario.empty = false;
  resetAdminStore();
}

export const FIXTURE_TOKEN_PREFIX = 'tm-fixture.';
/** Suffix of a fixture token that carries the Portal.Write scope (admin actions only). */
export const FIXTURE_WRITE_SUFFIX = '.write';

/** Read routes accept the Portal.Read fixture token only, as the server checks the scope. */
function userOf(request: Request): DemoUser | null {
  const h = request.headers.get('authorization') ?? '';
  const m = /^Bearer tm-fixture\.(viewer|engineer|lead|admin)$/.exec(h);
  return m ? USERS[m[1] as DemoUserId] : null;
}

function meta(extra: Partial<Meta> = {}): Meta {
  return { generated_at: new Date().toISOString(), data_as_of: new Date().toISOString(), ...extra };
}

function ok<T>(data: T, extra: Partial<Meta> = {}, page?: Page) {
  return HttpResponse.json(page ? { data, meta: meta(extra), page } : { data, meta: meta(extra) });
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

type Resolver = (args: {
  request: Request;
  params: PathParams;
  user: DemoUser;
  url: URL;
}) => Response | Promise<Response>;

function route(path: string, resolver: Resolver, opts: { classB?: boolean } = {}) {
  return http.get(path, ({ request, params }) => {
    const user = userOf(request);
    if (!user) return problem(401, 'E-API-02', 'Token missing or invalid', request);
    if (opts.classB && !user.engineerFamily) {
      return problem(403, 'E-API-03', 'This view needs an engineer-family role', request);
    }
    return resolver({ request, params, user, url: new URL(request.url) });
  });
}

/** Systems in scope after the project and system filters; outside scope -> null (E-API-04). */
function scoped(user: DemoUser, url: URL): string[] | null {
  let codes = user.systems;
  const project = url.searchParams.get('project');
  const system = url.searchParams.get('system');
  if (project) {
    codes = codes.filter((c) => SYSTEMS.find((s) => s.code === c)?.project === project);
    if (!codes.length) return null;
  }
  if (system) {
    codes = codes.filter((c) => c === system);
    if (!codes.length) return null;
  }
  return codes;
}

function scopeMeta(user: DemoUser, codes: string[]): Meta['scope'] {
  return {
    level: user.id === 'lead' || user.id === 'admin' ? 'all' : 'systems',
    projects: [
      ...new Set(codes.map((c) => SYSTEMS.find((s) => s.code === c)?.project ?? '')),
    ].sort(),
    systems: [...codes].sort(),
  };
}

function wantsNames(user: DemoUser, url: URL) {
  return url.searchParams.get('include') === 'names' && user.nameSystems.length > 0;
}

function runsResponse(user: DemoUser, url: URL, request: Request, podId?: string) {
  const codes = scoped(user, url);
  if (!codes) return problem(404, 'E-API-04', 'Not found', request);
  const status = url.searchParams.get('status');
  const owner = url.searchParams.get('owner');
  let rows = RUN_ROWS.filter((r) => codes.includes(r.system));
  if (podId) rows = rows.filter((r) => r.pod === podId);
  if (owner === 'me') rows = rows.filter((r) => r.engineer === user.me.pseudonym);
  if (status === 'open') rows = rows.filter((r) => r.status !== 'COMPLETED');
  else if (status === 'completed')
    rows = rows.filter(
      (r) => r.status === 'COMPLETED' && r.endReason !== 'aborted' && r.endReason !== 'cancelled',
    );
  else if (status === 'aborted') rows = rows.filter((r) => r.endReason === 'aborted');
  else if (status === 'cancelled') rows = rows.filter((r) => r.endReason === 'cancelled');
  else if (status) rows = rows.filter((r) => r.status === status);
  if (scenario.empty) rows = [];
  rows = [...rows].sort((a, b) => a.updatedMin - b.updatedMin);
  const limit = Math.min(100, Math.max(1, Number(url.searchParams.get('limit') ?? 25)));
  const start = Number(url.searchParams.get('cursor') ?? 0) || 0;
  const pageRows = rows.slice(start, start + limit);
  const next = start + limit < rows.length ? String(start + limit) : null;
  const names = wantsNames(user, url);
  const items = pageRows.map((r) =>
    runItem(r, user.me.pseudonym, names && user.nameSystems.includes(r.system)),
  );
  return ok({ items }, { scope: scopeMeta(user, codes) }, { limit, next_cursor: next });
}

export const handlers = [
  route('/v1/me', ({ user }) => ok(user.me)),
  route('/v1/status', () => ok(statusData(scenario.behind))),

  route('/v1/catalogue/summary', () => {
    const prod = SKILLS.filter((s) => s.status === 'production');
    return ok(
      {
        skills_in_production: scenario.empty ? 0 : prod.length,
        roles_covered: new Set(prod.map((s) => s.agent_role)).size,
        phases_covered: new Set(prod.map((s) => s.phase)).size,
        pods_ready: POD_ROWS.filter((p) => p.status !== 'draft').length,
        roles: ROLES.map(([id, code, label]) => ({
          id,
          code,
          label,
          skills_production: prod.filter((s) => s.agent_role === id).length,
          skills_pilot: SKILLS.filter((s) => s.agent_role === id && s.status === 'pilot').length,
        })),
        phases: PHASES,
        domains: [...new Set(prod.flatMap((s) => s.domains))].sort(),
        latest_release: {
          tag: 'v1.6.0',
          plugin_version: '1.6.0',
          released_at: '2026-10-01T08:00:00Z',
        },
      },
      { scope: { level: 'org' } },
    );
  }),

  route('/v1/catalogue/skills', ({ user, url }) => {
    const q = (url.searchParams.get('q') ?? '').toLowerCase();
    const role = url.searchParams.get('role');
    const statusParam = url.searchParams.get('status');
    const allowed = new Set(
      statusParam
        ? statusParam.split(',')
        : ['pilot', 'production', ...(user.engineerFamily ? ['draft'] : [])],
    );
    if (!user.engineerFamily) allowed.delete('draft');
    const limit = Number(url.searchParams.get('limit') ?? 25);
    const items = SKILLS.filter(
      (s) =>
        allowed.has(s.status) &&
        (!role || s.agent_role === role) &&
        (!q ||
          [s.id, s.title, s.summary, s.agent_role_label, s.phase, ...s.outputs]
            .join(' ')
            .toLowerCase()
            .includes(q)),
    )
      .map((s) => (scenario.empty ? { ...s, first_try_pass: null, first_try_n: 0 } : s))
      .sort((a, b) => a.agent_role.localeCompare(b.agent_role) || a.title.localeCompare(b.title))
      .slice(0, limit);
    return ok({ items }, { scope: { level: 'org' } }, { limit, next_cursor: null });
  }),

  route('/v1/catalogue/skills/:skillId', ({ params, user, request }) => {
    const card = SKILLS.find((s) => s.id === params.skillId);
    if (!card || (card.status === 'draft' && !user.engineerFamily)) {
      return problem(404, 'E-API-04', 'Skill not found', request);
    }
    return ok(skillDetail(card), { scope: { level: 'org' } });
  }),

  route(
    '/v1/catalogue/skills/:skillId/quality',
    ({ params, request }) => {
      if (!SKILLS.some((s) => s.id === params.skillId))
        return problem(404, 'E-API-04', 'Skill not found', request);
      return ok({
        skill_id: String(params.skillId),
        version: SKILLS.find((s) => s.id === params.skillId)?.current_version ?? '1.0.0',
        scope_level: 'systems',
        first_attempts: 52,
        causes: [
          { code: 'S1', label: 'Evidence below threshold', n: 9 },
          { code: 'H6', label: 'Stale design input', n: 5 },
          { code: 'H5', label: 'Missing trace link', n: 3 },
        ],
      });
    },
    { classB: true },
  ),

  route('/v1/catalogue/releases', ({ url }) => {
    const limit = Number(url.searchParams.get('limit') ?? 25);
    return ok(
      { items: RELEASES.slice(0, limit) },
      { scope: { level: 'org' } },
      { limit, next_cursor: null },
    );
  }),

  route('/v1/catalogue/pods', ({ user, url }) => {
    const limit = Number(url.searchParams.get('limit') ?? 25);
    const featured = url.searchParams.get('sort') === 'featured';
    const rows = [...POD_ROWS].sort((a, b) =>
      featured
        ? b.engagements - a.engagements
        : a.status.localeCompare(b.status) || a.title.localeCompare(b.title),
    );
    const items = rows.slice(0, limit).map((p) => podCard(p, !user.engineerFamily));
    return ok({ items }, { scope: { level: 'org' } }, { limit, next_cursor: null });
  }),

  route('/v1/pods/:podId', ({ params, user, request }) => {
    const p = POD_ROWS.find((x) => x.id === params.podId);
    if (!p) return problem(404, 'E-API-04', 'Pod not found', request);
    return ok(podDetail(p, !user.engineerFamily), { scope: { level: 'org' } });
  }),

  route('/v1/pods/:podId/metrics', ({ params, request }) => {
    if (!POD_ROWS.some((x) => x.id === params.podId))
      return problem(404, 'E-API-04', 'Pod not found', request);
    const m = scenario.empty ? null : POD_METRICS[String(params.podId)];
    return ok(m ? { status: 'ok', period: 'all', ...m } : { status: 'no_data' }, {
      scope: { level: 'org' },
    });
  }),

  route(
    '/v1/pods/:podId/runs',
    ({ params, user, url, request }) => {
      if (!POD_ROWS.some((x) => x.id === params.podId))
        return problem(404, 'E-API-04', 'Pod not found', request);
      return runsResponse(user, url, request, String(params.podId));
    },
    { classB: true },
  ),

  route(
    '/v1/pods/:podId/fit',
    ({ params, user, url, request }) => {
      const system = url.searchParams.get('system') ?? '';
      if (!user.systems.includes(system))
        return problem(404, 'E-API-04', 'System not found', request);
      return ok(
        {
          pod_id: String(params.podId),
          system,
          checks: [
            {
              key: 'product_repo_host',
              required: 'github',
              status: 'met',
              detail: '1 product repo(s) registered on GitHub',
            },
            {
              key: 'context_pack',
              required: 'fresh',
              status: system === 'SYS-INV' ? 'not_met' : 'met',
              detail: `Pack status ${system === 'SYS-INV' ? 'stale' : 'fresh'}`,
            },
            {
              key: 'docker',
              required: true,
              status: 'confirm_locally',
              detail: 'Not checkable from the server; confirm with tsl doctor',
            },
          ],
        },
        { scope: { level: 'systems', projects: [], systems: [system] } },
      );
    },
    { classB: true },
  ),

  route('/v1/pods/:podId/one-pager', ({ params, request }) => {
    const p = POD_ROWS.find((x) => x.id === params.podId);
    if (!p) return problem(404, 'E-API-04', 'Pod not found', request);
    const m = POD_METRICS[p.id];
    return ok(
      {
        pod_id: p.id,
        status: p.status,
        markdown: onePagerMarkdown(p),
        metrics: m ? { status: 'ok', period: 'all', ...m } : { status: 'no_data' },
        internal_only: p.status !== 'production',
      },
      { scope: { level: 'org' } },
    );
  }),

  route('/v1/capability-map', ({ url }) => {
    const audience = url.searchParams.get('audience') === 'shared' ? 'shared' : 'internal';
    return ok(capabilityMap(audience), { scope: { level: 'org' } });
  }),

  route('/v1/insights/business', ({ url }) => {
    const period = url.searchParams.get('period') ?? '90d';
    return ok(businessFor(period, scenario.empty), { scope: { level: 'org' } });
  }),

  route('/v1/me/home', ({ user }) => ok(homeFor(user), { scope: scopeMeta(user, user.systems) }), {
    classB: true,
  }),

  route(
    '/v1/insights/engineering/runs',
    ({ user, url, request }) => {
      const codes = scoped(user, url);
      if (!codes) return problem(404, 'E-API-04', 'Not found', request);
      return ok(engRuns(codes, scenario.empty), { scope: scopeMeta(user, codes) });
    },
    { classB: true },
  ),

  route(
    '/v1/insights/engineering/skills',
    ({ user, url, request }) => {
      const codes = scoped(user, url);
      if (!codes) return problem(404, 'E-API-04', 'Not found', request);
      const items = scenario.empty ? [] : ENG_SKILLS;
      return ok(
        { items },
        { scope: scopeMeta(user, codes) },
        { limit: items.length, next_cursor: null },
      );
    },
    { classB: true },
  ),

  route(
    '/v1/insights/engineering/usage',
    ({ user, url, request }) => {
      const codes = scoped(user, url);
      if (!codes) return problem(404, 'E-API-04', 'Not found', request);
      return ok(ENG_USAGE, { scope: scopeMeta(user, codes) });
    },
    { classB: true },
  ),

  route(
    '/v1/insights/engineering/health',
    ({ user, url, request }) => {
      const codes = scoped(user, url);
      if (!codes) return problem(404, 'E-API-04', 'Not found', request);
      return ok(engHealth(codes, user.telemetry), { scope: scopeMeta(user, codes) });
    },
    { classB: true },
  ),

  route('/v1/runs', ({ user, url, request }) => runsResponse(user, url, request), { classB: true }),

  route(
    '/v1/runs/:runId',
    ({ params, user, url, request }) => {
      const r = RUN_ROWS.find((x) => x.id === params.runId);
      if (!r || !user.systems.includes(r.system))
        return problem(404, 'E-API-04', 'Run not found', request);
      const names = wantsNames(user, url) && user.nameSystems.includes(r.system);
      return ok(runDetail(r, user.me.pseudonym, names), { scope: scopeMeta(user, user.systems) });
    },
    { classB: true },
  ),

  route('/v1/improvement/skills/:skillId', ({ params, user, request }) => {
    const allowed = user.me.roles.some(
      (g) =>
        g.role === 'eng_lead' ||
        g.role === 'admin' ||
        (g.role === 'skill_owner' && g.scope === params.skillId),
    );
    if (!allowed) return problem(403, 'E-API-03', 'Needs skill_owner, eng_lead or admin', request);
    if (!SKILLS.some((s) => s.id === params.skillId))
      return problem(404, 'E-API-04', 'Skill not found', request);
    return ok(improvementReport(String(params.skillId)), { scope: { level: 'org' } });
  }),
  ...adminHandlers,
];

/** Every handler's method and OpenAPI path, for the contract test (TC-POR-009). */
export const HANDLED_ROUTES = handlers.map((h) => ({
  method: String(h.info.method),
  path: String(h.info.path).replace(/:(\w+)/g, (_m, name: string) => `{${toSnake(name)}}`),
}));

function toSnake(s: string): string {
  return s.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`);
}

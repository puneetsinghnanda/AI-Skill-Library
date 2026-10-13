/**
 * TC-POR-009: mock fixtures and the typed client agree with the committed OpenAPI.
 * The OpenAPI declares read responses as open objects, so this checks routes, methods and query
 * parameters; the response field shapes are checked at compile time against api/types.ts.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { HANDLED_ROUTES } from '../mocks/handlers';
import { USERS } from '../mocks/fixtures';
import type { ResponseMap } from './types';

const spec = JSON.parse(
  readFileSync(resolve(__dirname, '../../../services/insights/openapi/openapi.json'), 'utf8'),
) as { paths: Record<string, Record<string, { parameters?: { name: string; in: string }[] }>> };

const CLIENT_ROUTES: (keyof ResponseMap)[] = [
  '/v1/me',
  '/v1/status',
  '/v1/catalogue/summary',
  '/v1/catalogue/skills',
  '/v1/catalogue/skills/{skill_id}',
  '/v1/catalogue/skills/{skill_id}/quality',
  '/v1/catalogue/releases',
  '/v1/catalogue/pods',
  '/v1/pods/{pod_id}',
  '/v1/pods/{pod_id}/metrics',
  '/v1/pods/{pod_id}/runs',
  '/v1/pods/{pod_id}/fit',
  '/v1/pods/{pod_id}/one-pager',
  '/v1/capability-map',
  '/v1/insights/business',
  '/v1/me/home',
  '/v1/insights/engineering/runs',
  '/v1/insights/engineering/skills',
  '/v1/insights/engineering/usage',
  '/v1/insights/engineering/health',
  '/v1/runs',
  '/v1/runs/{run_id}',
  '/v1/improvement/skills/{skill_id}',
];

/** Query parameters the screens send, per route (must exist in the OpenAPI). */
const QUERY_USED: Record<string, string[]> = {
  '/v1/catalogue/skills': ['q', 'role', 'status', 'period', 'limit'],
  '/v1/catalogue/skills/{skill_id}/quality': ['period'],
  '/v1/catalogue/releases': ['limit'],
  '/v1/catalogue/pods': ['limit', 'sort'],
  '/v1/pods/{pod_id}/metrics': ['period'],
  '/v1/pods/{pod_id}/runs': ['status', 'include'],
  '/v1/pods/{pod_id}/fit': ['system'],
  '/v1/capability-map': ['audience'],
  '/v1/insights/business': ['period'],
  '/v1/me/home': ['tz'],
  '/v1/insights/engineering/runs': ['project', 'system', 'period'],
  '/v1/insights/engineering/skills': ['project', 'system', 'period'],
  '/v1/insights/engineering/usage': ['project', 'system', 'period'],
  '/v1/insights/engineering/health': ['project', 'system', 'period'],
  '/v1/runs': ['project', 'system', 'period', 'owner', 'include', 'limit', 'cursor'],
  '/v1/runs/{run_id}': ['include'],
};

describe('contract with services/insights/openapi/openapi.json', () => {
  it.each(CLIENT_ROUTES)('client route %s is a GET in the OpenAPI', (path) => {
    expect(spec.paths[path]?.get).toBeDefined();
  });

  it.each(HANDLED_ROUTES.map((r) => [r.method, r.path]))(
    'mock %s %s exists in the OpenAPI',
    (method, path) => {
      expect(spec.paths[path]?.[method.toLowerCase()]).toBeDefined();
    },
  );

  it('mocks every route the client calls', () => {
    const mocked = new Set(HANDLED_ROUTES.map((r) => r.path));
    expect(CLIENT_ROUTES.filter((r) => !mocked.has(r))).toEqual([]);
  });

  it.each(Object.entries(QUERY_USED))('query parameters of %s exist', (path, names) => {
    const declared = (spec.paths[path]?.get?.parameters ?? [])
      .filter((p) => p.in === 'query')
      .map((p) => p.name);
    expect(names.filter((n) => !declared.includes(n))).toEqual([]);
  });

  it('the portal never calls a non-GET route (read-only portal, SDD-09 §1.3)', () => {
    expect(HANDLED_ROUTES.every((r) => r.method === 'GET')).toBe(true);
  });

  it('fixture users carry every /v1/me field the server returns (app/api/v1/me.py)', () => {
    const fields = [
      'pseudonym',
      'display_name',
      'role_label',
      'roles',
      'agent_role',
      'default_view',
      'can_switch_view',
      'can_reveal_names',
      'scope',
      'app_roles',
    ];
    for (const u of Object.values(USERS))
      expect(Object.keys(u.me).sort()).toEqual([...fields].sort());
  });
});

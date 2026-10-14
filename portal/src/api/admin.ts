/**
 * Typed client for the admin API (SDD-13 §7.2, SDD-09 §4.16): services/insights/app/api/v1/admin.py
 * and `POST /v1/keys/{key_id}/revoke` (app/api/v1/keys.py, SDD-07 §5.6).
 *
 * Request bodies are the OpenAPI request schemas (ClientIn, ConsentIn, ...), so a drift in the
 * Pydantic models fails `tsc`. Response bodies are open objects in the OpenAPI and are typed here
 * from the route code. Every call uses a `Portal.Write` token, requested only at the moment of the
 * action; every write is audited by the server (`audit_log`, SEC-01).
 *
 * The lists (`GET /v1/admin/...`, app/api/v1/admin_lists.py) use the ordinary `Portal.Read` token,
 * page with `next_cursor` and are refreshed after every successful admin action.
 */
import {
  infiniteQueryOptions,
  useInfiniteQuery,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query';
import type { components } from './schema';
import type { ApiClient, PostBody, PostPath, QueryOf } from './client';
import { useApi } from './queries';
import type { MeData } from './types';

type Schemas = components['schemas'];
export type ClientIn = Schemas['ClientIn'];
export type ConsentIn = Schemas['ConsentIn'];
export type ProjectIn = Schemas['ProjectIn'];
export type SystemIn = Schemas['SystemIn'];
export type RepoIn = Schemas['RepoIn'];
export type GrantIn = Schemas['GrantIn'];
export type ReasonIn = Schemas['ReasonIn'];
export type KeyRevokeIn = Schemas['RevokeBody'];

export type GrantRole = GrantIn['role'];
export type ScopeType = GrantIn['scope_type'];
export type ConsentScope = NonNullable<ConsentIn['scope']>[number];
export type KeyRevokeReason = KeyRevokeIn['reason'];

/* ------------------------------------------------------------------ responses (route code) */
export interface ClientCreated {
  id: string;
  code: string;
  denylist_version: number;
}
export interface ConsentResult {
  code: string;
  recorded_at: string | null;
  withdrawn_at: string | null;
}
export interface ProjectCreated {
  id: string;
  code: string;
  client: string;
}
export interface SystemCreated {
  id: string;
  code: string;
  project: string;
}
export interface GrantCreated {
  id: string;
  user: string;
  role: GrantRole;
  scope_type: ScopeType;
  scope: string | null;
}
export interface GrantRevoked {
  id: string;
  revoked_at: string | null;
}
export interface UserDeactivated {
  pseudonym: string;
  active: false;
  keys_revoked: string[];
  grants_revoked: number;
}
export interface KeyRevoked {
  key_id: string;
  revoked_at: string | null;
  revoked_reason: string;
  compromised_since: string | null;
}

/* ------------------------------------------------------------------ rules mirrored from the API */
/** Patterns from admin.py and keys.py; the server checks them again. */
export const PATTERNS = {
  client: /^CL-[0-9A-Z]{2,8}$/,
  project: /^PRJ-[0-9A-Z]{2,8}$/,
  system: /^SYS-[0-9A-Z]{2,8}$/,
  repo: /^[A-Za-z0-9_.-]{1,100}\/[A-Za-z0-9_.-]{1,100}$/,
  repoName: /^[a-z0-9][a-z0-9-]{0,60}$/,
  domain: /^[a-z][a-z0-9-]{1,30}$/,
  consentRef: /^[A-Z0-9-]{3,40}$/,
  user: /^eng-[0-9a-f]{4,8}$/,
  grantId: /^[0-9a-f-]{36}$/,
  keyId: /^key_[0-9A-HJKMNP-TV-Z]{26}$/,
} as const;

export const CONSENT_SCOPES: { value: ConsentScope; label: string }[] = [
  { value: 'code_processing', label: 'Code processing' },
  { value: 'companion_storage', label: 'Companion repo storage' },
  { value: 'product_prs', label: 'Pull requests to product repos' },
  { value: 'ci_webhook', label: 'CI webhook' },
];

/** ROLE_SCOPES in admin.py: the scope types each role may be granted at. */
export const ROLE_SCOPES: Record<GrantRole, ScopeType[]> = {
  viewer: ['org'],
  engineer: ['system'],
  tech_lead: ['system'],
  skill_owner: ['skill'],
  stage_approver: ['stage'],
  eng_lead: ['org', 'client', 'project'],
  admin: ['org'],
};

export const ROLE_LABELS: Record<GrantRole, string> = {
  viewer: 'Viewer',
  engineer: 'Engineer',
  tech_lead: 'Tech lead',
  skill_owner: 'Skill owner',
  stage_approver: 'Stage approver',
  eng_lead: 'Engineering lead',
  admin: 'Admin',
};

export const STAGES = ['requirements', 'design', 'build', 'test', 'operate'] as const;

/** Reasons an admin may give for revoking someone's key (ADMIN_REASONS in keys.py). */
export const ADMIN_KEY_REASONS: { value: KeyRevokeReason; label: string }[] = [
  { value: 'offboarded', label: 'Offboarded' },
  { value: 'lost_device', label: 'Lost device' },
  { value: 'compromised', label: 'Compromised' },
  { value: 'user_request', label: 'User request' },
  { value: 'admin_other', label: 'Other (admin)' },
];

/** The admin screens are for the Entra app role Admin only (SDD-07 §3.2, SDD-13 §7.2). */
export function isAdmin(me: MeData): boolean {
  return me.app_roles.includes('Admin');
}

/* ------------------------------------------------------------------ calls */
type Call<I, O> = (api: ApiClient, input: I) => Promise<O>;

function post<P extends PostPath, I, O>(
  path: P,
  pick: (input: I) => { body: PostBody<P>; path?: Record<string, string> },
): Call<I, O> {
  return (api, input) => {
    const r = pick(input);
    return api.post<P, O>(path, r.body, r.path);
  };
}

export const admin = {
  createClient: post<'/v1/admin/clients', ClientIn, ClientCreated>('/v1/admin/clients', (b) => ({
    body: b,
  })),
  consent: post<
    '/v1/admin/clients/{code}/consent',
    { code: string; body: ConsentIn },
    ConsentResult
  >('/v1/admin/clients/{code}/consent', (i) => ({ body: i.body, path: { code: i.code } })),
  createProject: post<'/v1/admin/projects', ProjectIn, ProjectCreated>(
    '/v1/admin/projects',
    (b) => ({ body: b }),
  ),
  createSystem: post<'/v1/admin/systems', SystemIn, SystemCreated>('/v1/admin/systems', (b) => ({
    body: b,
  })),
  grantRole: post<'/v1/admin/role-grants', GrantIn, GrantCreated>('/v1/admin/role-grants', (b) => ({
    body: b,
  })),
  revokeGrant: post<
    '/v1/admin/role-grants/{grant_id}/revoke',
    { grantId: string; body: ReasonIn },
    GrantRevoked
  >('/v1/admin/role-grants/{grant_id}/revoke', (i) => ({
    body: i.body,
    path: { grant_id: i.grantId },
  })),
  deactivateUser: post<
    '/v1/admin/users/{pseudonym}/deactivate',
    { pseudonym: string; body: ReasonIn },
    UserDeactivated
  >('/v1/admin/users/{pseudonym}/deactivate', (i) => ({
    body: i.body,
    path: { pseudonym: i.pseudonym },
  })),
  revokeKey: post<'/v1/keys/{key_id}/revoke', { keyId: string; body: KeyRevokeIn }, KeyRevoked>(
    '/v1/keys/{key_id}/revoke',
    (i) => ({ body: i.body, path: { key_id: i.keyId } }),
  ),
} as const;

/** Every POST route the admin screens call (checked against the OpenAPI by contract.test.ts). */
export const ADMIN_ROUTES: PostPath[] = [
  '/v1/admin/clients',
  '/v1/admin/clients/{code}/consent',
  '/v1/admin/projects',
  '/v1/admin/systems',
  '/v1/admin/role-grants',
  '/v1/admin/role-grants/{grant_id}/revoke',
  '/v1/admin/users/{pseudonym}/deactivate',
  '/v1/keys/{key_id}/revoke',
];

/** One mutation per admin action. Writes are never retried automatically; lists refresh after. */
export function useAdminAction<I, O>(call: Call<I, O>) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation<O, unknown, I>({
    mutationFn: (input) => call(api, input),
    retry: false,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin'] }),
  });
}

/* ------------------------------------------------------------------ lists (Portal.Read) */
/** Every GET list route the admin screens call (checked against the OpenAPI by contract.test.ts). */
export const ADMIN_LIST_ROUTES = [
  '/v1/admin/clients',
  '/v1/admin/projects',
  '/v1/admin/systems',
  '/v1/admin/role-grants',
  '/v1/admin/users',
  '/v1/admin/users/{pseudonym}/keys',
] as const;

export type ClientsQuery = QueryOf<'/v1/admin/clients'>;
export type ProjectsQuery = QueryOf<'/v1/admin/projects'>;
export type SystemsQuery = QueryOf<'/v1/admin/systems'>;
export type GrantsQuery = QueryOf<'/v1/admin/role-grants'>;
export type UsersQuery = QueryOf<'/v1/admin/users'>;
export type KeysQuery = QueryOf<'/v1/admin/users/{pseudonym}/keys'>;

const paged = {
  initialPageParam: null as string | null,
  getNextPageParam: (last: { page: { next_cursor: string | null } }) => last.page.next_cursor,
  staleTime: 0,
};

export const adminLists = {
  clients: (api: ApiClient, query: ClientsQuery) =>
    infiniteQueryOptions({
      queryKey: ['admin', 'clients', query] as const,
      queryFn: ({ signal, pageParam }) =>
        api.get('/v1/admin/clients', { query: { ...query, cursor: pageParam } }, signal),
      ...paged,
    }),
  projects: (api: ApiClient, query: ProjectsQuery) =>
    infiniteQueryOptions({
      queryKey: ['admin', 'projects', query] as const,
      queryFn: ({ signal, pageParam }) =>
        api.get('/v1/admin/projects', { query: { ...query, cursor: pageParam } }, signal),
      ...paged,
    }),
  systems: (api: ApiClient, query: SystemsQuery) =>
    infiniteQueryOptions({
      queryKey: ['admin', 'systems', query] as const,
      queryFn: ({ signal, pageParam }) =>
        api.get('/v1/admin/systems', { query: { ...query, cursor: pageParam } }, signal),
      ...paged,
    }),
  grants: (api: ApiClient, query: GrantsQuery) =>
    infiniteQueryOptions({
      queryKey: ['admin', 'role-grants', query] as const,
      queryFn: ({ signal, pageParam }) =>
        api.get('/v1/admin/role-grants', { query: { ...query, cursor: pageParam } }, signal),
      ...paged,
    }),
  users: (api: ApiClient, query: UsersQuery) =>
    infiniteQueryOptions({
      queryKey: ['admin', 'users', query] as const,
      queryFn: ({ signal, pageParam }) =>
        api.get('/v1/admin/users', { query: { ...query, cursor: pageParam } }, signal),
      ...paged,
    }),
  keys: (api: ApiClient, pseudonym: string, query: KeysQuery) =>
    infiniteQueryOptions({
      queryKey: ['admin', 'keys', pseudonym, query] as const,
      queryFn: ({ signal, pageParam }) =>
        api.get(
          '/v1/admin/users/{pseudonym}/keys',
          { path: { pseudonym }, query: { ...query, cursor: pageParam } },
          signal,
        ),
      ...paged,
    }),
};

export const useAdminClients = (q: ClientsQuery = {}) =>
  useInfiniteQuery(adminLists.clients(useApi(), q));
export const useAdminProjects = (q: ProjectsQuery = {}) =>
  useInfiniteQuery(adminLists.projects(useApi(), q));
export const useAdminSystems = (q: SystemsQuery = {}) =>
  useInfiniteQuery(adminLists.systems(useApi(), q));
export const useAdminGrants = (q: GrantsQuery = {}) =>
  useInfiniteQuery(adminLists.grants(useApi(), q));
export const useAdminUsers = (q: UsersQuery = {}) =>
  useInfiniteQuery(adminLists.users(useApi(), q));
export const useAdminKeys = (pseudonym: string, q: KeysQuery = {}) =>
  useInfiniteQuery(adminLists.keys(useApi(), pseudonym, q));

/**
 * Fetch wrapper for the read API (SDD-09 §3.5, §5.1): bearer token, X-Request-ID, problem+json to
 * ApiError, one silent token refresh on 401 then sign-in. Paths and query parameters are typed
 * from the generated OpenAPI (schema.d.ts); response bodies from types.ts.
 *
 * `post` exists only for the admin screens (SDD-09 §4.16): it asks the auth port for a
 * `Portal.Write` token at the moment of the action and is typed to the OpenAPI POST routes.
 */
import type { AuthPort } from '../auth/port';
import type { paths } from './schema';
import type { Problem, ResponseMap } from './types';

/* ------------------------------------------------------------------ typing from the OpenAPI */
type GetOp<P extends keyof paths> = NonNullable<paths[P]['get']>;

/** Every path in the OpenAPI that has a GET operation. */
export type GetPath = {
  [P in keyof paths]-?: [GetOp<P>] extends [never] ? never : P;
}[keyof paths];

/** Compile-time guard: every route in ResponseMap must be a GET route of the committed OpenAPI. */
type AssertSubset<A, B> = [A] extends [B] ? true : never;
const _routesExist: AssertSubset<keyof ResponseMap, GetPath> = true;
void _routesExist;

export type ApiPath = keyof ResponseMap & GetPath;

type PostOp<P extends keyof paths> = NonNullable<paths[P]['post']>;

/** Every path in the OpenAPI that has a POST operation. */
export type PostPath = {
  [P in keyof paths]-?: [PostOp<P>] extends [never] ? never : P;
}[keyof paths];

/** JSON request body of a POST route, from the OpenAPI (Pydantic models of the route). */
export type PostBody<P extends PostPath> =
  PostOp<P> extends { requestBody: { content: { 'application/json': infer B } } } ? B : never;

export type QueryOf<P extends ApiPath> =
  GetOp<P> extends { parameters: { query?: infer Q } } ? NonNullable<Q> : never;

type PathParamsOf<P extends ApiPath> =
  GetOp<P> extends { parameters: { path: infer X } } ? X : never;

export type RequestOptions<P extends ApiPath> = ([PathParamsOf<P>] extends [never]
  ? { path?: undefined }
  : { path: PathParamsOf<P> }) & { query?: QueryOf<P> };

/* ------------------------------------------------------------------ errors */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail: string;
  readonly requestId: string;
  readonly retryAfterS: number | null;

  constructor(init: {
    status: number;
    code: string;
    detail: string;
    requestId: string;
    retryAfterS?: number | null;
  }) {
    super(`${init.code}: ${init.detail}`);
    this.name = 'ApiError';
    this.status = init.status;
    this.code = init.code;
    this.detail = init.detail;
    this.requestId = init.requestId;
    this.retryAfterS = init.retryAfterS ?? null;
  }

  get isForbidden(): boolean {
    return this.status === 403;
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }
}

export function requestId(): string {
  const c = globalThis.crypto;
  if (c && typeof c.randomUUID === 'function') return c.randomUUID();
  const b = new Uint8Array(16);
  c.getRandomValues(b);
  b[6] = ((b[6] ?? 0) & 0x0f) | 0x40;
  b[8] = ((b[8] ?? 0) & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, '0')).join('');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

/* ------------------------------------------------------------------ client */
export interface ApiClientOptions {
  baseUrl: string;
  auth: Pick<AuthPort, 'getToken' | 'signIn' | 'credentials'>;
  fetchImpl?: typeof fetch;
}

/** Header the insights service requires on cookie-authenticated writes (E-API-07, ADR 0006). */
export const CSRF_HEADER = { 'X-Requested-With': 'truminds-portal' } as const;

export function buildUrl(
  base: string,
  template: string,
  path?: Record<string, string> | undefined,
  query?: Record<string, unknown> | undefined,
): string {
  let p = template;
  for (const [k, v] of Object.entries(path ?? {})) {
    p = p.replace(`{${k}}`, encodeURIComponent(v));
  }
  if (/\{[^}]+\}/.test(p)) throw new Error(`Missing path parameter in ${template}`);
  const origin =
    base || (typeof window !== 'undefined' ? window.location.origin : 'http://localhost');
  const url = new URL(p, origin.endsWith('/') ? origin : `${origin}/`);
  for (const [k, v] of Object.entries(query ?? {})) {
    if (v === undefined || v === null || v === '') continue;
    url.searchParams.set(k, String(v));
  }
  return url.toString();
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly auth: Pick<AuthPort, 'getToken' | 'signIn' | 'credentials'>;
  private readonly fetchImpl: typeof fetch;

  constructor(opts: ApiClientOptions) {
    this.baseUrl = opts.baseUrl;
    this.auth = opts.auth;
    this.fetchImpl = opts.fetchImpl ?? ((...args) => globalThis.fetch(...args));
  }

  async get<P extends ApiPath>(
    path: P,
    options?: RequestOptions<P>,
    signal?: AbortSignal,
  ): Promise<ResponseMap[P]> {
    const url = buildUrl(
      this.baseUrl,
      path,
      options?.path as Record<string, string> | undefined,
      options?.query as Record<string, unknown> | undefined,
    );
    return (await this.send({ url, method: 'GET', write: false }, signal, false)) as ResponseMap[P];
  }

  /** Admin writes only (SDD-09 §4.16). Uses a Portal.Write token; never retried automatically. */
  async post<P extends PostPath, R>(
    path: P,
    body: PostBody<P>,
    pathParams?: Record<string, string>,
  ): Promise<R> {
    const url = buildUrl(this.baseUrl, path, pathParams);
    return (await this.send(
      { url, method: 'POST', body: JSON.stringify(body), write: true },
      undefined,
      false,
    )) as R;
  }

  private async send(
    req: { url: string; method: 'GET' | 'POST'; body?: string; write: boolean },
    signal: AbortSignal | undefined,
    refreshed: boolean,
  ): Promise<unknown> {
    const rid = requestId();
    const cookie = this.auth.credentials === 'cookie';
    const headers: Record<string, string> = {
      Accept: 'application/json',
      'X-Request-ID': rid,
    };
    if (cookie) {
      // GitHub sign-in (ADR 0006): the HttpOnly session cookie is the credential; writes carry the
      // CSRF header. There is no token in the browser to refresh.
      if (req.method !== 'GET') Object.assign(headers, CSRF_HEADER);
    } else {
      try {
        const opts = {
          ...(refreshed ? { forceRefresh: true } : {}),
          ...(req.write ? { write: true } : {}),
        };
        const token = await this.auth.getToken(Object.keys(opts).length ? opts : undefined);
        headers.Authorization = `Bearer ${token}`;
      } catch (e) {
        throw new ApiError({
          status: 401,
          code: 'E-API-02',
          detail: e instanceof Error ? e.message : 'Sign-in is needed.',
          requestId: rid,
        });
      }
    }
    let res: Response;
    try {
      if (req.body !== undefined) headers['Content-Type'] = 'application/json';
      res = await this.fetchImpl(req.url, {
        method: req.method,
        headers,
        ...(req.body !== undefined ? { body: req.body } : {}),
        credentials: cookie ? 'include' : 'omit',
        signal,
      });
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') throw e;
      throw new ApiError({
        status: 0,
        code: 'NETWORK',
        detail: 'The insights service could not be reached.',
        requestId: rid,
      });
    }
    if (res.ok) return res.json();

    if (res.status === 401 && !refreshed && !cookie) return this.send(req, signal, true);
    const err = await toApiError(res, rid);
    // A write keeps the admin's form on screen; reads fall back to an interactive sign-in.
    if (res.status === 401 && !req.write) void this.auth.signIn();
    throw err;
  }
}

async function toApiError(res: Response, rid: string): Promise<ApiError> {
  let problem: Partial<Problem> = {};
  const type = res.headers.get('content-type') ?? '';
  if (type.includes('json')) {
    try {
      problem = (await res.json()) as Partial<Problem>;
    } catch {
      problem = {};
    }
  }
  const retry = Number(res.headers.get('retry-after'));
  return new ApiError({
    status: res.status,
    code: problem.code ?? `HTTP-${res.status}`,
    detail: problem.detail ?? problem.title ?? res.statusText ?? 'Request failed',
    requestId: problem.request_id ?? res.headers.get('x-request-id') ?? rid,
    retryAfterS: Number.isFinite(retry) && retry > 0 ? retry : null,
  });
}

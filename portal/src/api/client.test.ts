import { describe, expect, it, vi } from 'vitest';
import { ApiClient, ApiError, buildUrl } from './client';
import { retryDelay, shouldRetry } from './queries';

function client(responses: Response[], token = vi.fn(async () => 'tok')) {
  const fetchImpl = vi.fn(async () => {
    const r = responses.shift();
    if (!r) throw new Error('no more responses');
    return r;
  });
  const signIn = vi.fn(async () => undefined);
  const api = new ApiClient({
    baseUrl: 'https://portal.example.invalid',
    auth: { getToken: token, signIn },
    fetchImpl,
  });
  return { api, fetchImpl, signIn, token };
}

const json = (body: unknown, status = 200, type = 'application/json') =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': type } });

describe('buildUrl', () => {
  it('fills path parameters and drops empty query values', () => {
    expect(
      buildUrl(
        'https://h.invalid',
        '/v1/catalogue/skills/{skill_id}',
        { skill_id: 'threat-model' },
        { period: '90d', q: '', role: undefined },
      ),
    ).toBe('https://h.invalid/v1/catalogue/skills/threat-model?period=90d');
  });

  it('refuses a template with a missing path parameter', () => {
    expect(() => buildUrl('https://h.invalid', '/v1/runs/{run_id}')).toThrow(
      /Missing path parameter/,
    );
  });
});

describe('ApiClient', () => {
  it('sends the bearer token, Accept and a UUID X-Request-ID', async () => {
    const { api, fetchImpl } = client([json({ data: { behind: false }, meta: {} })]);
    await api.get('/v1/status');
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('https://portal.example.invalid/v1/status');
    const h = init.headers as Record<string, string>;
    expect(h.Authorization).toBe('Bearer tok');
    expect(h['X-Request-ID']).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    );
    expect(init.method).toBe('GET');
  });

  it('turns problem+json into an ApiError with code and request id', async () => {
    const { api } = client([
      json(
        {
          code: 'E-API-04',
          title: 'Not found',
          status: 404,
          detail: 'Run not found.',
          request_id: 'rid-1',
        },
        404,
        'application/problem+json',
      ),
    ]);
    const err = await api
      .get('/v1/runs/{run_id}', { path: { run_id: 'run_X' } })
      .catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({
      status: 404,
      code: 'E-API-04',
      detail: 'Run not found.',
      requestId: 'rid-1',
    });
  });

  it('retries a 401 once with a forced token refresh, then starts sign-in', async () => {
    const token = vi.fn(async () => 'tok');
    const { api, signIn, fetchImpl } = client(
      [
        json({ code: 'E-API-02' }, 401, 'application/problem+json'),
        json({ code: 'E-API-02' }, 401, 'application/problem+json'),
      ],
      token,
    );
    await expect(api.get('/v1/me')).rejects.toMatchObject({ status: 401 });
    expect(fetchImpl).toHaveBeenCalledTimes(2);
    expect(token).toHaveBeenNthCalledWith(2, { forceRefresh: true });
    expect(signIn).toHaveBeenCalledTimes(1);
  });

  it('succeeds after the silent refresh without asking to sign in', async () => {
    const { api, signIn } = client([json({}, 401), json({ data: { ok: 1 }, meta: {} })]);
    await expect(api.get('/v1/me')).resolves.toMatchObject({ data: { ok: 1 } });
    expect(signIn).not.toHaveBeenCalled();
  });

  it('reports a network failure as code NETWORK', async () => {
    const fetchImpl = vi.fn(async () => {
      throw new TypeError('fetch failed');
    });
    const api = new ApiClient({
      baseUrl: 'https://h.invalid',
      auth: { getToken: async () => 't', signIn: async () => undefined },
      fetchImpl,
    });
    await expect(api.get('/v1/me')).rejects.toMatchObject({ status: 0, code: 'NETWORK' });
  });

  it('reads Retry-After on 429', async () => {
    const { api } = client([
      new Response('{}', {
        status: 429,
        headers: { 'Retry-After': '3', 'Content-Type': 'application/json' },
      }),
    ]);
    const err = (await api.get('/v1/me').catch((e: unknown) => e)) as ApiError;
    expect(err.retryAfterS).toBe(3);
    expect(retryDelay(0, err)).toBe(3000);
  });
});

describe('retry policy (SDD-09 §3.5)', () => {
  const e = (status: number) => new ApiError({ status, code: 'X', detail: '', requestId: 'r' });
  it('retries network errors and 5xx twice, 4xx never, 429 once', () => {
    expect(shouldRetry(0, e(503))).toBe(true);
    expect(shouldRetry(1, e(503))).toBe(true);
    expect(shouldRetry(2, e(503))).toBe(false);
    expect(shouldRetry(0, e(0))).toBe(true);
    expect(shouldRetry(0, e(404))).toBe(false);
    expect(shouldRetry(0, e(403))).toBe(false);
    expect(shouldRetry(0, e(429))).toBe(true);
    expect(shouldRetry(1, e(429))).toBe(false);
  });
});

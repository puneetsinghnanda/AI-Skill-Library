/** GitHub provider mode (ADR 0006, SDD-09 §3.4.1): cookie credentials, CSRF header, sign-in gate. */
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ApiClient } from '../api/client';
import { isTestEnvironment, TestEnvironmentNotice } from '../app/StatusBanner';
import { identityProvider } from '../config/env';
import { githubAuthPort, returnPath, signInUrl } from './github';

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

function fetchQueue(responses: Response[]) {
  return vi.fn(async (...args: Parameters<typeof fetch>) => {
    void args;
    const r = responses.shift();
    if (!r) throw new Error('no more responses');
    return r;
  });
}

describe('identityProvider', () => {
  it('defaults to entra and accepts github only', () => {
    expect(identityProvider(undefined)).toBe('entra');
    expect(identityProvider('')).toBe('entra');
    expect(identityProvider('GitHub ')).toBe('github');
    expect(identityProvider('okta')).toBe('entra');
  });
});

describe('ApiClient in cookie mode', () => {
  function cookieClient(responses: Response[]) {
    const fetchImpl = fetchQueue(responses);
    const getToken = vi.fn(async () => 'never');
    const signIn = vi.fn(async () => undefined);
    const api = new ApiClient({
      baseUrl: 'https://portal.example.invalid',
      auth: { credentials: 'cookie', getToken, signIn },
      fetchImpl,
    });
    return { api, fetchImpl, getToken, signIn };
  }

  it('sends the session cookie, no Authorization header, and never asks for a token', async () => {
    const { api, fetchImpl, getToken } = cookieClient([json({ data: { behind: false } })]);
    await api.get('/v1/status');
    const init = fetchImpl.mock.calls[0]?.[1] as RequestInit;
    const h = init.headers as Record<string, string>;
    expect(init.credentials).toBe('include');
    expect(h.Authorization).toBeUndefined();
    expect(h['X-Requested-With']).toBeUndefined(); // reads need no CSRF header
    expect(getToken).not.toHaveBeenCalled();
  });

  it('adds X-Requested-With: truminds-portal on writes', async () => {
    const { api, fetchImpl } = cookieClient([json({ id: 'g1' }, 201)]);
    await api.post('/v1/admin/projects', { client: 'CL-DEMO', code: 'PRJ-NEW' });
    const init = fetchImpl.mock.calls[0]?.[1] as RequestInit;
    const h = init.headers as Record<string, string>;
    expect(init.method).toBe('POST');
    expect(init.credentials).toBe('include');
    expect(h['X-Requested-With']).toBe('truminds-portal');
    expect(h.Authorization).toBeUndefined();
  });

  it('on 401 goes to sign-in without a token-refresh retry', async () => {
    const { api, fetchImpl, signIn } = cookieClient([
      json({ code: 'E-API-02', detail: 'Missing bearer token' }, 401),
    ]);
    await expect(api.get('/v1/status')).rejects.toMatchObject({ status: 401, code: 'E-API-02' });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(signIn).toHaveBeenCalledTimes(1);
  });

  it('bearer mode is unchanged (Entra)', async () => {
    const fetchImpl = fetchQueue([json({ data: { behind: false } })]);
    const api = new ApiClient({
      baseUrl: 'https://portal.example.invalid',
      auth: { getToken: async () => 'tok', signIn: async () => undefined },
      fetchImpl,
    });
    await api.get('/v1/status');
    const init = fetchImpl.mock.calls[0]?.[1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok');
    expect(init.credentials).toBe('omit');
  });
});

describe('githubAuthPort', () => {
  it('builds a same-origin sign-in URL with a safe return path', () => {
    expect(signInUrl('', '/skills?q=a')).toBe('/auth/github/login?return_to=%2Fskills%3Fq%3Da');
    expect(signInUrl('https://svc.example.invalid/', '/x')).toBe(
      'https://svc.example.invalid/auth/github/login?return_to=%2Fx',
    );
    expect(returnPath('//evil.example')).toBe('/');
    expect(returnPath('/auth/callback')).toBe('/');
  });

  it('shows "Sign in with GitHub" when there is no session', async () => {
    const fetchImpl = fetchQueue([json({ code: 'E-API-02' }, 401)]);
    const port = githubAuthPort({ apiBaseUrl: '', fetchImpl, currentPath: () => '/pods' });
    render(
      <port.Gate>
        <p>secret page</p>
      </port.Gate>,
    );
    const link = await screen.findByRole('link', { name: 'Sign in with GitHub' });
    expect(link.getAttribute('href')).toBe('/auth/github/login?return_to=%2Fpods');
    expect(screen.queryByText('secret page')).toBeNull();
    const init = fetchImpl.mock.calls[0]?.[1] as RequestInit;
    expect(fetchImpl.mock.calls[0]?.[0]).toBe('/v1/me');
    expect(init.credentials).toBe('include');
  });

  it.each([200, 403])('renders the app when /v1/me answers %i', async (status) => {
    const fetchImpl = fetchQueue([json({}, status)]);
    const port = githubAuthPort({ apiBaseUrl: '', fetchImpl });
    render(
      <port.Gate>
        <p>the portal</p>
      </port.Gate>,
    );
    expect(await screen.findByText('the portal')).toBeTruthy();
  });

  it('signs out with a CSRF-protected POST /auth/logout, then goes home', async () => {
    const fetchImpl = fetchQueue([new Response(null, { status: 204 })]);
    const navigate = vi.fn();
    const port = githubAuthPort({ apiBaseUrl: '', fetchImpl, navigate });
    expect(port.credentials).toBe('cookie');
    await port.signOut();
    const [url, init] = fetchImpl.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/auth/logout');
    expect(init.method).toBe('POST');
    expect(init.credentials).toBe('include');
    expect((init.headers as Record<string, string>)['X-Requested-With']).toBe('truminds-portal');
    expect(navigate).toHaveBeenCalledWith('/');
  });

  it('signIn navigates to the service login route', async () => {
    const navigate = vi.fn();
    const port = githubAuthPort({ apiBaseUrl: '', navigate, currentPath: () => '/insights' });
    await port.signIn();
    expect(navigate).toHaveBeenCalledWith('/auth/github/login?return_to=%2Finsights');
    await expect(port.getToken()).rejects.toThrow(/session cookie/);
  });
});

describe('TEST ENVIRONMENT banner', () => {
  it('is on for "test" from the build or from /v1/status', () => {
    expect(isTestEnvironment('', 'test')).toBe(true);
    expect(isTestEnvironment('TEST', undefined)).toBe(true);
    expect(isTestEnvironment('prod', 'staging')).toBe(false);
    render(<TestEnvironmentNotice />);
    expect(screen.getByRole('note', { name: 'Test environment' }).textContent).toMatch(
      /TEST ENVIRONMENT/,
    );
  });
});

/**
 * Microsoft Entra ID sign-in through MSAL (ADR 0002, SDD-09 §3.4): authorization code with PKCE,
 * redirect flow, tokens in memory only (cacheLocation "memoryStorage", SEC-01 §5.11). A reload
 * re-acquires a token silently from the Entra session (ssoSilent), else redirects to sign in.
 *
 * With memory storage, MSAL must not reload the page after the redirect (navigateToLoginRequestUrl
 * false), or the tokens it just stored would be lost; the original path travels in `state` and is
 * restored with history.replaceState before the router starts.
 */
import {
  BrowserCacheLocation,
  EventType,
  InteractionRequiredAuthError,
  InteractionStatus,
  InteractionType,
  PublicClientApplication,
  type AuthenticationResult,
  type Configuration,
} from '@azure/msal-browser';
import { MsalAuthenticationTemplate, useMsal } from '@azure/msal-react';
import type { ReactNode } from 'react';
import type { Env } from '../config/env';
import type { AuthPort } from './port';

export function msalConfig(env: Env): Configuration {
  return {
    auth: {
      clientId: env.clientId,
      authority: `https://login.microsoftonline.com/${env.tenantId}`,
      redirectUri: env.redirectUri || `${window.location.origin}/auth/callback`,
      postLogoutRedirectUri: `${window.location.origin}/`,
      navigateToLoginRequestUrl: false,
    },
    cache: {
      cacheLocation: BrowserCacheLocation.MemoryStorage,
      storeAuthStateInCookie: false,
    },
    system: {
      allowNativeBroker: false,
    },
  };
}

/** Only same-origin paths are restored after sign-in (no open redirect). */
export function safeReturnPath(state: string | null | undefined): string | null {
  if (!state || !state.startsWith('/') || state.startsWith('//') || state.startsWith('/auth/'))
    return null;
  return state;
}

function currentPath(): string {
  return `${window.location.pathname}${window.location.search}${window.location.hash}`;
}

export async function createMsal(env: Env): Promise<PublicClientApplication> {
  if (!env.clientId || !env.tenantId) {
    throw new Error('VITE_ENTRA_CLIENT_ID and VITE_ENTRA_TENANT_ID must be set at build time.');
  }
  const pca = new PublicClientApplication(msalConfig(env));
  await pca.initialize();
  pca.addEventCallback((event) => {
    if (
      event.eventType === EventType.LOGIN_SUCCESS ||
      event.eventType === EventType.SSO_SILENT_SUCCESS
    ) {
      const result = event.payload as AuthenticationResult | null;
      if (result?.account) pca.setActiveAccount(result.account);
    }
  });
  const result = await pca.handleRedirectPromise();
  if (result?.account) pca.setActiveAccount(result.account);
  const back = safeReturnPath(result?.state);
  if (back) window.history.replaceState(null, '', back);
  else if (window.location.pathname.startsWith('/auth/callback'))
    window.history.replaceState(null, '', '/');

  if (!pca.getActiveAccount()) {
    const first = pca.getAllAccounts()[0];
    if (first) pca.setActiveAccount(first);
  }
  if (!pca.getActiveAccount()) {
    try {
      const sso = await pca.ssoSilent({ scopes: [env.apiScope] });
      pca.setActiveAccount(sso.account);
    } catch {
      /* no Entra session yet: the gate starts an interactive redirect */
    }
  }
  return pca;
}

export function msalAuthPort(pca: PublicClientApplication, env: Env): AuthPort {
  const scopes = [env.apiScope];

  function Gate({ children }: { children: ReactNode }) {
    return (
      <MsalAuthenticationTemplate
        interactionType={InteractionType.Redirect}
        authenticationRequest={{ scopes, state: currentPath() }}
        loadingComponent={SigningIn}
        errorComponent={SignInError}
      >
        {children}
      </MsalAuthenticationTemplate>
    );
  }

  return {
    async getToken(options) {
      const account = pca.getActiveAccount() ?? pca.getAllAccounts()[0];
      if (!account) throw new Error('Not signed in');
      // Portal.Write only for admin actions, requested incrementally (SDD-09 §4.16).
      const wanted = options?.write ? [env.apiWriteScope] : scopes;
      try {
        const r = await pca.acquireTokenSilent({
          scopes: wanted,
          account,
          forceRefresh: options?.forceRefresh ?? false,
        });
        return r.accessToken;
      } catch (e) {
        if (e instanceof InteractionRequiredAuthError) {
          await pca.acquireTokenRedirect({ scopes: wanted, account, state: currentPath() });
        }
        throw e;
      }
    },
    async signIn() {
      await pca.loginRedirect({ scopes, state: currentPath() });
    },
    async signOut() {
      const account = pca.getActiveAccount() ?? undefined;
      await pca.logoutRedirect({ account });
    },
    Gate,
  };
}

function SigningIn() {
  const { inProgress } = useMsal();
  return (
    <main id="main" className="tm-wrap pt-40" aria-busy="true">
      <p role="status">
        {inProgress === InteractionStatus.None
          ? 'Preparing sign-in…'
          : 'Signing you in with your company account…'}
      </p>
    </main>
  );
}

function SignInError({ error }: { error: Error | null }) {
  return (
    <main id="main" className="tm-wrap pt-40">
      <h1 className="page-h1">Sign-in did not complete</h1>
      <p className="tm-sub">
        Sign in with your Truminds company account. If this keeps happening, ask an admin to check
        your access.
      </p>
      {error?.name ? (
        <p className="xsmall text-2">
          Error <span className="mono">{error.name}</span>
        </p>
      ) : null}
      <a className="tm-btn btn-primary mt-16" href="/">
        Try again
      </a>
    </main>
  );
}

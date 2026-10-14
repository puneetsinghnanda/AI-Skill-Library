/**
 * The one seam between the portal and sign-in. Production wires Microsoft Entra ID through MSAL
 * (auth/msal.ts, ADR 0002). Tests and the explicit demo build wire a token-cache fixture instead
 * (demo/fixtureAuth.ts); the production bundle never contains it (TC-POR-010).
 */
import { createContext, useContext, type ComponentType, type ReactNode } from 'react';

export interface TokenOptions {
  forceRefresh?: boolean;
  write?: boolean;
}

/**
 * How API calls carry the credential: `bearer` (Entra access token from `getToken`) or `cookie`
 * (GitHub sign-in, ADR 0006: the insights service holds the token; the browser sends the
 * HttpOnly session cookie with `credentials: 'include'`).
 */
export type CredentialMode = 'bearer' | 'cookie';

export interface AuthPort {
  /** Defaults to `bearer`. */
  credentials?: CredentialMode;
  /**
   * Access token for the read API scope (VITE_API_SCOPE), or, with `write: true`, for the
   * `Portal.Write` scope (VITE_API_WRITE_SCOPE). The write scope is requested incrementally, only
   * when an admin submits an admin action (SDD-09 §4.16, SDD-07 §9).
   */
  getToken(options?: TokenOptions): Promise<string>;
  /** Start an interactive sign-in (redirect flow). */
  signIn(): Promise<void>;
  /** Sign out (redirect) after the caller has cleared the query cache. */
  signOut(): Promise<void>;
  /** Wraps the signed-in part of the app (MsalAuthenticationTemplate in production). */
  Gate: ComponentType<{ children: ReactNode }>;
}

const AuthContext = createContext<AuthPort | null>(null);

export function AuthProvider({ port, children }: { port: AuthPort; children: ReactNode }) {
  return <AuthContext.Provider value={port}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthPort {
  const port = useContext(AuthContext);
  if (!port) throw new Error('AuthProvider is missing');
  return port;
}

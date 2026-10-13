/**
 * The one seam between the portal and sign-in. Production wires Microsoft Entra ID through MSAL
 * (auth/msal.ts, ADR 0002). Tests and the explicit demo build wire a token-cache fixture instead
 * (demo/fixtureAuth.ts); the production bundle never contains it (TC-POR-010).
 */
import { createContext, useContext, type ComponentType, type ReactNode } from 'react';

export interface AuthPort {
  /** Access token for the read API scope (VITE_API_SCOPE). */
  getToken(options?: { forceRefresh?: boolean }): Promise<string>;
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

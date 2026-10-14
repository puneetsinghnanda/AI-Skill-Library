/**
 * Production entry: Entra ID sign-in through MSAL, or, when the build sets
 * VITE_IDENTITY_PROVIDER=github (test phase, ADR 0006), GitHub sign-in through the insights service
 * session cookie. No mocks, no test fixture, no bypass.
 */
import { MsalProvider } from '@azure/msal-react';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { createPortal, Portal } from '../app/App';
import { env } from '../config/env';
import { githubAuthPort } from './github';
import { createMsal, msalAuthPort } from './msal';

export async function startProd(root: HTMLElement): Promise<void> {
  try {
    if (env.identityProvider === 'github') {
      const deps = createPortal(githubAuthPort({ apiBaseUrl: env.apiBaseUrl }));
      createRoot(root).render(
        <StrictMode>
          <Portal {...deps} />
        </StrictMode>,
      );
      return;
    }
    const pca = await createMsal(env);
    const deps = createPortal(msalAuthPort(pca, env));
    createRoot(root).render(
      <StrictMode>
        <MsalProvider instance={pca}>
          <Portal {...deps} />
        </MsalProvider>
      </StrictMode>,
    );
  } catch (e) {
    createRoot(root).render(
      <main id="main" className="tm-wrap pt-40">
        <h1 className="page-h1">The portal could not start</h1>
        <p className="tm-sub">
          Sign-in is not configured for this environment. Ask the portal owner.
        </p>
        <p className="xsmall text-2">{e instanceof Error ? e.message : 'Unknown error'}</p>
      </main>,
    );
  }
}

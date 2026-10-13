import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider, createBrowserRouter, type RouteObject } from 'react-router-dom';
import { ApiClient } from '../api/client';
import { ApiProvider, retryDelay, shouldRetry } from '../api/queries';
import { AuthProvider, type AuthPort } from '../auth/port';
import { env } from '../config/env';
import { buildRoutes } from './routes';

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: shouldRetry,
        retryDelay,
        refetchOnWindowFocus: false,
      },
    },
  });
}

/** Opt in to React Router v7 behaviour now, so the upgrade changes nothing. */
export const ROUTER_FUTURE = {
  v7_relativeSplatPath: true,
  v7_fetcherPersist: true,
  v7_normalizeFormMethod: true,
  v7_partialHydration: true,
  v7_skipActionErrorRevalidation: true,
} as const;

export interface PortalDeps {
  auth: AuthPort;
  api: ApiClient;
  queryClient: QueryClient;
  router: ReturnType<typeof createBrowserRouter>;
}

/** MsalProvider (outside, in production) > QueryClientProvider > RouterProvider (SDD-09 §3.2). */
export function Portal({ auth, api, queryClient, router }: PortalDeps) {
  return (
    <AuthProvider port={auth}>
      <QueryClientProvider client={queryClient}>
        <ApiProvider client={api}>
          <RouterProvider router={router} future={{ v7_startTransition: true }} />
        </ApiProvider>
      </QueryClientProvider>
    </AuthProvider>
  );
}

/** Wires the portal for a given auth port. `createRouter` lets tests use a memory router. */
export function createPortal(
  auth: AuthPort,
  options: {
    banner?: ReactNode;
    createRouter?: (routes: RouteObject[]) => ReturnType<typeof createBrowserRouter>;
    queryClient?: QueryClient;
  } = {},
): PortalDeps {
  const queryClient = options.queryClient ?? createQueryClient();
  const api = new ApiClient({ baseUrl: env.apiBaseUrl, auth });
  const routes = buildRoutes({ qc: queryClient, api, Gate: auth.Gate, banner: options.banner });
  const router = (
    options.createRouter ?? ((r) => createBrowserRouter(r, { future: ROUTER_FUTURE }))
  )(routes);
  return { auth, api, queryClient, router };
}

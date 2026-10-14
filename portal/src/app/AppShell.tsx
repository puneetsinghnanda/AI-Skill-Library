import { Suspense, useEffect, useRef, type ReactNode } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { useMe } from '../api/queries';
import { ApiError } from '../api/client';
import { env } from '../config/env';
import { ErrorState, Skeleton, SkeletonGrid } from '../components/States';
import { NoAccess } from '../screens/NoAccess';
import { StatusBanner, TestEnvironmentBanner } from './StatusBanner';
import { TopBar } from './TopBar';
import { ViewProvider } from './ViewContext';

/** On route change, focus moves to the screen's h1 (SDD-09 §8) and the page scrolls to the top. */
function useRouteFocus() {
  const { pathname } = useLocation();
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    window.scrollTo?.(0, 0);
    let tries = 0;
    let handle = 0;
    const tryFocus = () => {
      const h1 = document.querySelector<HTMLElement>('main h1');
      if (h1) {
        h1.focus();
        return;
      }
      if (tries++ < 30) handle = window.requestAnimationFrame(tryFocus);
      else document.getElementById('main')?.focus();
    };
    handle = window.requestAnimationFrame(tryFocus);
    return () => window.cancelAnimationFrame(handle);
  }, [pathname]);
}

export function PageSkeleton() {
  return (
    <div className="tm-wrap pt-40 stack gap-24" aria-busy="true">
      <Skeleton height={48} label="Loading page" />
      <SkeletonGrid count={4} />
      <Skeleton height={240} />
    </div>
  );
}

function Footer() {
  const help = env.helpUrl;
  return (
    <footer className="site-footer">
      <div className="tm-wrap">
        <span>
          Truminds AI Skill Library · {env.envName} · build{' '}
          <span className="mono">{env.buildId}</span>
        </span>
        {help ? <a href={help}>Need help?</a> : <Link to="/get-started#help">Need help?</Link>}
      </div>
    </footer>
  );
}

function Frame({ banner, children }: { banner?: ReactNode; children: ReactNode }) {
  useRouteFocus();
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to main content
      </a>
      <TestEnvironmentBanner />
      <TopBar />
      {banner}
      <StatusBanner />
      <main id="main" tabIndex={-1}>
        {children}
      </main>
      <Footer />
    </>
  );
}

/** Board Main: top bar, status banner, routed screen, footer (SDD-09 §4.1). */
export function AppShell({ banner }: { banner?: ReactNode }) {
  const me = useMe();
  if (me.isPending) {
    return (
      <>
        <div className="topbar">
          <div className="topbar-inner" />
        </div>
        <main id="main">
          <PageSkeleton />
        </main>
      </>
    );
  }
  if (me.isError) {
    if (me.error instanceof ApiError && me.error.status === 403)
      return (
        <NoAccess
          banner={banner}
          // GitHub sign-in (ADR 0006): the service names the pseudonym an admin must grant to.
          detail={env.identityProvider === 'github' ? me.error.detail : undefined}
        />
      );
    return (
      <main id="main" className="tm-wrap pt-40">
        <h1 className="page-h1">The portal could not load</h1>
        <div className="mt-16">
          <ErrorState error={me.error} onRetry={() => void me.refetch()} />
        </div>
      </main>
    );
  }
  const data = me.data.data;
  if (data.roles.length === 0) return <NoAccess banner={banner} />;
  return (
    <ViewProvider me={data}>
      <Frame banner={banner}>
        <Suspense fallback={<PageSkeleton />}>
          <Outlet />
        </Suspense>
      </Frame>
    </ViewProvider>
  );
}

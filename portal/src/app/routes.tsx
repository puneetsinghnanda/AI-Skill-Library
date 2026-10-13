/**
 * Routes (SDD-09 §3.3). `/pods/builder` is matched before `/pods/:podId`. Screens are split into
 * their own bundles. The persona switch changes the layout only; the server decides access.
 */
import { lazy, type ComponentType, type ReactNode } from 'react';
import { Navigate, type RouteObject } from 'react-router-dom';
import type { QueryClient } from '@tanstack/react-query';
import type { ApiClient } from '../api/client';
import { prefetch, q } from '../api/queries';
import { AuthCallback } from '../screens/AuthCallback';
import { AppShell } from './AppShell';
import { useView } from './ViewContext';

const HomeBusiness = lazy(() => import('../screens/HomeBusiness'));
const HomeEngineer = lazy(() => import('../screens/HomeEngineer'));
const HowItWorks = lazy(() => import('../screens/HowItWorks'));
const Skills = lazy(() => import('../screens/Skills'));
const SkillDetail = lazy(() => import('../screens/SkillDetail'));
const GetStarted = lazy(() => import('../screens/GetStarted'));
const Pods = lazy(() => import('../screens/Pods'));
const PodDetail = lazy(() => import('../screens/PodDetail'));
const PodOnePager = lazy(() => import('../screens/PodOnePager'));
const PodBuilder = lazy(() => import('../screens/PodBuilder'));
const InsightsBusiness = lazy(() => import('../screens/InsightsBusiness'));
const InsightsEngineering = lazy(() => import('../screens/InsightsEngineering'));
const CapabilityMapShare = lazy(() => import('../screens/CapabilityMapShare'));
const ImprovementReport = lazy(() => import('../screens/ImprovementReport'));
const RunDetail = lazy(() => import('../screens/RunDetail'));
const NotFound = lazy(() => import('../screens/NotFound'));

function HomeRoute() {
  const { view } = useView();
  return view === 'engineer' ? <HomeEngineer /> : <HomeBusiness />;
}

function InsightsRoute() {
  const { view } = useView();
  return view === 'engineer' ? <InsightsEngineering /> : <InsightsBusiness />;
}

/** Engineer-only screens: a Business view is sent to Insights (Doc 4 §2.0.1, TC-POR-003). */
function EngineerOnly({ children }: { children: ReactNode }) {
  const { view } = useView();
  if (view !== 'engineer') return <Navigate to="/insights" replace />;
  return <>{children}</>;
}

export interface RouteDeps {
  qc: QueryClient;
  api: ApiClient;
  Gate: ComponentType<{ children: ReactNode }>;
  banner?: ReactNode;
}

export function buildRoutes({ qc, api, Gate, banner }: RouteDeps): RouteObject[] {
  return [
    { path: '/auth/callback', element: <AuthCallback /> },
    {
      path: '/',
      element: (
        <Gate>
          <AppShell banner={banner} />
        </Gate>
      ),
      children: [
        { index: true, element: <HomeRoute /> },
        { path: 'how-it-works', element: <HowItWorks /> },
        { path: 'skills', element: <Skills /> },
        {
          path: 'skills/:skillId',
          element: <SkillDetail />,
          loader: ({ params }) => {
            if (params.skillId) prefetch(qc, q.skill(api, params.skillId));
            return null;
          },
        },
        { path: 'get-started', element: <GetStarted /> },
        { path: 'pods', element: <Pods /> },
        { path: 'pods/builder', element: <PodBuilder /> },
        {
          path: 'pods/:podId',
          element: <PodDetail />,
          loader: ({ params }) => {
            if (params.podId) prefetch(qc, q.pod(api, params.podId));
            return null;
          },
        },
        { path: 'pods/:podId/one-pager', element: <PodOnePager /> },
        { path: 'insights', element: <InsightsRoute /> },
        {
          path: 'insights/engineering/:tab',
          element: (
            <EngineerOnly>
              <InsightsEngineering />
            </EngineerOnly>
          ),
        },
        { path: 'insights/capability-map/share', element: <CapabilityMapShare /> },
        {
          path: 'insights/skills/:skillId/improvement',
          element: (
            <EngineerOnly>
              <ImprovementReport />
            </EngineerOnly>
          ),
        },
        {
          path: 'runs/:runId',
          element: (
            <EngineerOnly>
              <RunDetail />
            </EngineerOnly>
          ),
        },
        { path: '*', element: <NotFound /> },
      ],
    },
  ];
}

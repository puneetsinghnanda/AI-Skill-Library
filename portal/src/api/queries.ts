/**
 * Query-key factory and one hook per read endpoint (SDD-09 §3.5).
 *
 * staleTime: catalogue and pods 5 min; insights and runs 60 s (refetch on focus); /v1/me 10 min;
 * /v1/status 60 s. Nothing polls faster than 60 s (views refresh every 5 min, SDD-08 §10.3).
 */
import { createContext, createElement, useContext, type ReactNode } from 'react';
import {
  infiniteQueryOptions,
  queryOptions,
  useInfiniteQuery,
  useQuery,
  type QueryClient,
} from '@tanstack/react-query';
import { ApiError, type ApiClient, type QueryOf } from './client';

const MIN = 60_000;
export const STALE = {
  catalogue: 5 * MIN,
  insights: MIN,
  me: 10 * MIN,
  status: MIN,
} as const;

/* ------------------------------------------------------------------ client context */
const ApiContext = createContext<ApiClient | null>(null);

export function ApiProvider({ client, children }: { client: ApiClient; children: ReactNode }) {
  return createElement(ApiContext.Provider, { value: client }, children);
}

export function useApi(): ApiClient {
  const c = useContext(ApiContext);
  if (!c) throw new Error('ApiProvider is missing');
  return c;
}

/* ------------------------------------------------------------------ retry policy */
/** Network errors and 5xx: 2 retries with backoff; 429 once after Retry-After; other 4xx none. */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError) {
    if (error.status === 429) return failureCount < 1;
    if (error.status >= 400 && error.status < 500) return false;
  }
  return failureCount < 2;
}

export function retryDelay(attempt: number, error: unknown): number {
  if (error instanceof ApiError && error.status === 429 && error.retryAfterS) {
    return error.retryAfterS * 1000;
  }
  return Math.min(1000 * 2 ** attempt, 8000);
}

/* ------------------------------------------------------------------ keys */
type Q<P extends Parameters<ApiClient['get']>[0]> = QueryOf<P>;
export type SkillsParams = Q<'/v1/catalogue/skills'>;
export type PodsParams = Q<'/v1/catalogue/pods'>;
export type RunsParams = Q<'/v1/runs'>;
export type EngParams = Q<'/v1/insights/engineering/runs'>;

export const keys = {
  me: () => ['me'] as const,
  status: () => ['status'] as const,
  summary: () => ['catalogue', 'summary'] as const,
  skills: (p: SkillsParams) => ['catalogue', 'skills', p] as const,
  skill: (id: string) => ['catalogue', 'skill', id] as const,
  skillQuality: (id: string, p: Q<'/v1/catalogue/skills/{skill_id}/quality'>) =>
    ['catalogue', 'skill', id, 'quality', p] as const,
  releases: (limit: number) => ['catalogue', 'releases', limit] as const,
  pods: (p: PodsParams) => ['catalogue', 'pods', p] as const,
  pod: (id: string) => ['pods', id] as const,
  podMetrics: (id: string, period: string) => ['pods', id, 'metrics', period] as const,
  podRuns: (id: string, p: Q<'/v1/pods/{pod_id}/runs'>) => ['runs', 'pod', id, p] as const,
  podFit: (id: string, system: string) => ['pods', id, 'fit', system] as const,
  podOnePager: (id: string) => ['pods', id, 'one-pager'] as const,
  capabilityMap: (audience: 'internal' | 'shared') => ['capability-map', audience] as const,
  business: (period: string) => ['insights', 'business', period] as const,
  home: (tz: string) => ['me', 'home', tz] as const,
  engRuns: (p: EngParams) => ['insights', 'engineering', 'runs', p] as const,
  engSkills: (p: EngParams) => ['insights', 'engineering', 'skills', p] as const,
  engUsage: (p: EngParams) => ['insights', 'engineering', 'usage', p] as const,
  engHealth: (p: EngParams) => ['insights', 'engineering', 'health', p] as const,
  runs: (p: RunsParams) => ['runs', p] as const,
  run: (id: string, names: boolean) => ['runs', 'detail', id, names] as const,
  improvement: (skillId: string) => ['improvement', skillId] as const,
};

/* ------------------------------------------------------------------ query options */
export const q = {
  me: (api: ApiClient) =>
    queryOptions({
      queryKey: keys.me(),
      queryFn: ({ signal }) => api.get('/v1/me', undefined, signal),
      staleTime: STALE.me,
    }),
  status: (api: ApiClient) =>
    queryOptions({
      queryKey: keys.status(),
      queryFn: ({ signal }) => api.get('/v1/status', undefined, signal),
      staleTime: STALE.status,
      refetchInterval: STALE.status,
    }),
  summary: (api: ApiClient) =>
    queryOptions({
      queryKey: keys.summary(),
      queryFn: ({ signal }) => api.get('/v1/catalogue/summary', undefined, signal),
      staleTime: STALE.catalogue,
    }),
  skills: (api: ApiClient, p: SkillsParams) =>
    queryOptions({
      queryKey: keys.skills(p),
      queryFn: ({ signal }) => api.get('/v1/catalogue/skills', { query: p }, signal),
      staleTime: STALE.catalogue,
    }),
  skill: (api: ApiClient, id: string) =>
    queryOptions({
      queryKey: keys.skill(id),
      queryFn: ({ signal }) =>
        api.get('/v1/catalogue/skills/{skill_id}', { path: { skill_id: id } }, signal),
      staleTime: STALE.catalogue,
    }),
  skillQuality: (api: ApiClient, id: string, p: Q<'/v1/catalogue/skills/{skill_id}/quality'>) =>
    queryOptions({
      queryKey: keys.skillQuality(id, p),
      queryFn: ({ signal }) =>
        api.get(
          '/v1/catalogue/skills/{skill_id}/quality',
          { path: { skill_id: id }, query: p },
          signal,
        ),
      staleTime: STALE.insights,
    }),
  releases: (api: ApiClient, limit: number) =>
    queryOptions({
      queryKey: keys.releases(limit),
      queryFn: ({ signal }) => api.get('/v1/catalogue/releases', { query: { limit } }, signal),
      staleTime: STALE.catalogue,
    }),
  pods: (api: ApiClient, p: PodsParams) =>
    queryOptions({
      queryKey: keys.pods(p),
      queryFn: ({ signal }) => api.get('/v1/catalogue/pods', { query: p }, signal),
      staleTime: STALE.catalogue,
    }),
  pod: (api: ApiClient, id: string) =>
    queryOptions({
      queryKey: keys.pod(id),
      queryFn: ({ signal }) => api.get('/v1/pods/{pod_id}', { path: { pod_id: id } }, signal),
      staleTime: STALE.catalogue,
    }),
  podMetrics: (api: ApiClient, id: string, period: string) =>
    queryOptions({
      queryKey: keys.podMetrics(id, period),
      queryFn: ({ signal }) =>
        api.get('/v1/pods/{pod_id}/metrics', { path: { pod_id: id }, query: { period } }, signal),
      staleTime: STALE.catalogue,
    }),
  podRuns: (api: ApiClient, id: string, p: Q<'/v1/pods/{pod_id}/runs'>) =>
    queryOptions({
      queryKey: keys.podRuns(id, p),
      queryFn: ({ signal }) =>
        api.get('/v1/pods/{pod_id}/runs', { path: { pod_id: id }, query: p }, signal),
      staleTime: STALE.insights,
      refetchOnWindowFocus: true,
    }),
  podFit: (api: ApiClient, id: string, system: string) =>
    queryOptions({
      queryKey: keys.podFit(id, system),
      queryFn: ({ signal }) =>
        api.get('/v1/pods/{pod_id}/fit', { path: { pod_id: id }, query: { system } }, signal),
      staleTime: STALE.insights,
    }),
  podOnePager: (api: ApiClient, id: string) =>
    queryOptions({
      queryKey: keys.podOnePager(id),
      queryFn: ({ signal }) =>
        api.get('/v1/pods/{pod_id}/one-pager', { path: { pod_id: id } }, signal),
      staleTime: STALE.catalogue,
    }),
  capabilityMap: (api: ApiClient, audience: 'internal' | 'shared') =>
    queryOptions({
      queryKey: keys.capabilityMap(audience),
      queryFn: ({ signal }) => api.get('/v1/capability-map', { query: { audience } }, signal),
      staleTime: STALE.catalogue,
    }),
  business: (api: ApiClient, period: string) =>
    queryOptions({
      queryKey: keys.business(period),
      queryFn: ({ signal }) => api.get('/v1/insights/business', { query: { period } }, signal),
      staleTime: STALE.insights,
      refetchOnWindowFocus: true,
    }),
  home: (api: ApiClient, tz: string) =>
    queryOptions({
      queryKey: keys.home(tz),
      queryFn: ({ signal }) => api.get('/v1/me/home', { query: { tz } }, signal),
      staleTime: STALE.insights,
      refetchOnWindowFocus: true,
    }),
  engRuns: (api: ApiClient, p: EngParams) =>
    queryOptions({
      queryKey: keys.engRuns(p),
      queryFn: ({ signal }) => api.get('/v1/insights/engineering/runs', { query: p }, signal),
      staleTime: STALE.insights,
      refetchOnWindowFocus: true,
    }),
  engSkills: (api: ApiClient, p: EngParams) =>
    queryOptions({
      queryKey: keys.engSkills(p),
      queryFn: ({ signal }) => api.get('/v1/insights/engineering/skills', { query: p }, signal),
      staleTime: STALE.insights,
      refetchOnWindowFocus: true,
    }),
  engUsage: (api: ApiClient, p: EngParams) =>
    queryOptions({
      queryKey: keys.engUsage(p),
      queryFn: ({ signal }) => api.get('/v1/insights/engineering/usage', { query: p }, signal),
      staleTime: STALE.insights,
      refetchOnWindowFocus: true,
    }),
  engHealth: (api: ApiClient, p: EngParams) =>
    queryOptions({
      queryKey: keys.engHealth(p),
      queryFn: ({ signal }) => api.get('/v1/insights/engineering/health', { query: p }, signal),
      staleTime: STALE.insights,
      refetchOnWindowFocus: true,
    }),
  runs: (api: ApiClient, p: RunsParams) =>
    infiniteQueryOptions({
      queryKey: keys.runs(p),
      queryFn: ({ signal, pageParam }) =>
        api.get('/v1/runs', { query: { ...p, cursor: pageParam ?? undefined } }, signal),
      initialPageParam: null as string | null,
      getNextPageParam: (last) => last.page.next_cursor,
      staleTime: STALE.insights,
      refetchOnWindowFocus: true,
    }),
  run: (api: ApiClient, id: string, names: boolean) =>
    queryOptions({
      queryKey: keys.run(id, names),
      queryFn: ({ signal }) =>
        api.get(
          '/v1/runs/{run_id}',
          { path: { run_id: id }, query: names ? { include: 'names' } : {} },
          signal,
        ),
      staleTime: STALE.insights,
      refetchOnWindowFocus: true,
    }),
  improvement: (api: ApiClient, skillId: string) =>
    queryOptions({
      queryKey: keys.improvement(skillId),
      queryFn: ({ signal }) =>
        api.get('/v1/improvement/skills/{skill_id}', { path: { skill_id: skillId } }, signal),
      staleTime: STALE.insights,
    }),
};

/* ------------------------------------------------------------------ hooks */
export const useMe = () => useQuery(q.me(useApi()));
export const useStatus = () => useQuery(q.status(useApi()));
export const useSummary = () => useQuery(q.summary(useApi()));
export const useSkills = (p: SkillsParams, enabled = true) =>
  useQuery({ ...q.skills(useApi(), p), enabled });
export const useSkill = (id: string) => useQuery(q.skill(useApi(), id));
export const useSkillQuality = (
  id: string,
  p: Q<'/v1/catalogue/skills/{skill_id}/quality'>,
  enabled: boolean,
) => useQuery({ ...q.skillQuality(useApi(), id, p), enabled });
export const useReleases = (limit = 1) => useQuery(q.releases(useApi(), limit));
export const usePods = (p: PodsParams, enabled = true) =>
  useQuery({ ...q.pods(useApi(), p), enabled });
export const usePod = (id: string) => useQuery(q.pod(useApi(), id));
export const usePodMetrics = (id: string, period: string, enabled = true) =>
  useQuery({ ...q.podMetrics(useApi(), id, period), enabled });
export const usePodRuns = (id: string, p: Q<'/v1/pods/{pod_id}/runs'>, enabled: boolean) =>
  useQuery({ ...q.podRuns(useApi(), id, p), enabled });
export const usePodFit = (id: string, system: string) =>
  useQuery({ ...q.podFit(useApi(), id, system), enabled: system !== '' });
export const usePodOnePager = (id: string) => useQuery(q.podOnePager(useApi(), id));
export const useCapabilityMap = (audience: 'internal' | 'shared') =>
  useQuery(q.capabilityMap(useApi(), audience));
export const useBusiness = (period: string) => useQuery(q.business(useApi(), period));
export const useHome = (tz: string) => useQuery(q.home(useApi(), tz));
export const useEngRuns = (p: EngParams) => useQuery(q.engRuns(useApi(), p));
export const useEngSkills = (p: EngParams) => useQuery(q.engSkills(useApi(), p));
export const useEngUsage = (p: EngParams) => useQuery(q.engUsage(useApi(), p));
export const useEngHealth = (p: EngParams) => useQuery(q.engHealth(useApi(), p));
export const useRuns = (p: RunsParams, enabled = true) =>
  useInfiniteQuery({ ...q.runs(useApi(), p), enabled });
export const useRun = (id: string, names: boolean) => useQuery(q.run(useApi(), id, names));
export const useImprovement = (skillId: string) => useQuery(q.improvement(useApi(), skillId));

/** Route loaders prefetch the screen's main query so the screen renders once (§3.5). */
export function prefetch(
  qc: QueryClient,
  opts: ReturnType<(typeof q)[Exclude<keyof typeof q, 'runs'>]>,
) {
  void qc.prefetchQuery(opts as Parameters<QueryClient['prefetchQuery']>[0]);
}

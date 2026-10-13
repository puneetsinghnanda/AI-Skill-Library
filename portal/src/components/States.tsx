import type { ReactNode } from 'react';
import { ApiError } from '../api/client';

/** Skeleton block with the final layout size; no whole-page spinners (SDD-09 §3.6). */
export function Skeleton({ height = 96, label }: { height?: number; label?: string }) {
  return (
    <div
      className="skeleton"
      style={{ height }}
      role="status"
      aria-label={label ?? 'Loading'}
      aria-busy="true"
    />
  );
}

export function SkeletonGrid({
  count = 4,
  height = 96,
  cls = 'g-200',
}: {
  count?: number;
  height?: number;
  cls?: string;
}) {
  return (
    <div className={`grid ${cls}`}>
      {Array.from({ length: count }, (_, i) => (
        <Skeleton key={i} height={height} />
      ))}
    </div>
  );
}

/** Empty list: says what to do next (Doc 4 §2.0.5). */
export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="tm-card empty" style={{ textAlign: 'center', padding: 40 }}>
      <p className="m-0 strong" style={{ fontSize: 16 }}>
        {title}
      </p>
      {children ? (
        <p className="body text-2" style={{ margin: '6px 0 0' }}>
          {children}
        </p>
      ) : null}
    </div>
  );
}

export function errorWords(e: unknown): {
  title: string;
  code: string | null;
  requestId: string | null;
  detail: string | null;
} {
  if (e instanceof ApiError) {
    if (e.status === 403) {
      return {
        title: 'You do not have access to this view.',
        code: e.code,
        requestId: e.requestId,
        detail: null,
      };
    }
    if (e.status === 404) {
      return {
        title: 'We could not find this. It may not exist, or it is outside your scope.',
        code: e.code,
        requestId: e.requestId,
        detail: null,
      };
    }
    if (e.status === 400) {
      return {
        title: 'Some filters are not valid. Reset the filters and try again.',
        code: e.code,
        requestId: e.requestId,
        detail: e.detail,
      };
    }
    if (e.status === 429) {
      return {
        title: 'Too many requests. Wait a moment and try again.',
        code: e.code,
        requestId: e.requestId,
        detail: null,
      };
    }
    if (e.status === 0) {
      return {
        title: 'The insights service could not be reached.',
        code: e.code,
        requestId: e.requestId,
        detail: null,
      };
    }
    return {
      title: 'This section could not be loaded.',
      code: e.code,
      requestId: e.requestId,
      detail: e.detail,
    };
  }
  return { title: 'This section could not be loaded.', code: null, requestId: null, detail: null };
}

/** Error card: plain words, the error code and the request id; the rest of the page still renders. */
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const w = errorWords(error);
  return (
    <div className="tm-card error-card" role="alert">
      <p className="m-0 strong">{w.title}</p>
      {w.detail ? (
        <p className="body text-2" style={{ margin: '6px 0 0' }}>
          {w.detail}
        </p>
      ) : null}
      {w.code || w.requestId ? (
        <p className="xsmall text-2" style={{ margin: '8px 0 0' }}>
          {w.code ? (
            <>
              Error <span className="mono">{w.code}</span>
            </>
          ) : null}
          {w.code && w.requestId ? ' · ' : null}
          {w.requestId ? (
            <>
              Request id <span className="mono">{w.requestId}</span>
            </>
          ) : null}
        </p>
      ) : null}
      {onRetry ? (
        <button type="button" className="tm-btn btn-ghost mt-12" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  );
}

interface QueryLike<T> {
  data: T | undefined;
  error: unknown;
  isPending: boolean;
  isError: boolean;
  refetch: () => unknown;
}

/** Renders a query's loading, error or data state for one section. */
export function Section<T>({
  query,
  skeleton,
  children,
}: {
  query: QueryLike<T>;
  skeleton?: ReactNode;
  children: (data: T) => ReactNode;
}) {
  if (query.isPending) return <>{skeleton ?? <Skeleton />}</>;
  if (query.isError || query.data === undefined) {
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  }
  return <>{children(query.data)}</>;
}

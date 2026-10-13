import { Link, useParams } from 'react-router-dom';
import { usePod, usePodOnePager } from '../api/queries';
import { PageTitle } from '../components/Heading';
import { SafeMarkdown } from '../components/SafeMarkdown';
import { ErrorState, Skeleton } from '../components/States';
import { Badge } from '../components/StatusBadge';
import { localDate, percent } from '../lib/format';

/** Pod one-pager print view (SDD-09 §4.10): the pod's one-pager.md with the current metrics. */
export default function PodOnePager() {
  const { podId = '' } = useParams();
  const page = usePodOnePager(podId);
  const pod = usePod(podId);
  const title = pod.data?.data.title ?? 'Pod one-pager';
  return (
    <section className="tm-wrap pt-32 pb-56 stack gap-16">
      <div className="row between gap-12 no-print">
        <Link className="tm-link" to={`/pods/${podId}`}>
          ← Back to the pod
        </Link>
        <button type="button" className="tm-btn btn-primary" onClick={() => window.print()}>
          Print or save as PDF
        </button>
      </div>
      <PageTitle title={`${title} one-pager`}>{title}</PageTitle>
      {page.isPending ? (
        <Skeleton height={320} />
      ) : page.isError ? (
        <ErrorState error={page.error} />
      ) : (
        <>
          {page.data.data.internal_only ? (
            <Badge tone="input" className="self-start">
              {page.data.data.status === 'pilot' ? 'Pilot · internal only' : 'Internal only'}
            </Badge>
          ) : null}
          <div className="tm-card">
            {page.data.data.markdown ? (
              <SafeMarkdown source={page.data.data.markdown} />
            ) : (
              <p className="body text-2 m-0">This pod has no one-pager text yet.</p>
            )}
          </div>
          <div className="tm-card stack gap-6">
            <h2 className="h3">Track record</h2>
            {page.data.data.metrics.status === 'no_data' ? (
              <p className="body m-0">
                No data yet. A track record appears after 5 completed runs.
              </p>
            ) : (
              <p className="body m-0">
                {percent(page.data.data.metrics.first_try_pass) ?? 'No data yet'} first-try pass ·{' '}
                {page.data.data.metrics.systems_served} systems served ·{' '}
                {page.data.data.metrics.prs_merged} PRs merged
              </p>
            )}
            <p className="m-0 xsmall text-2">
              Aggregates only · {localDate(page.data.meta.generated_at)}
            </p>
          </div>
        </>
      )}
    </section>
  );
}

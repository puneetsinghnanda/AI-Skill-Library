import { Link } from 'react-router-dom';
import { useCapabilityMap } from '../api/queries';
import { CapabilityMapTable } from '../components/CapabilityMapTable';
import { PageTitle } from '../components/Heading';
import { StatTile } from '../components/StatTile';
import { EmptyState, ErrorState, Skeleton } from '../components/States';
import { count, localDate, percent } from '../lib/format';

/**
 * Shared capability map print view (SDD-09 §6): the server's `audience=shared` response, which
 * never carries pilot skills or their count. Users print or save as PDF; there is no public link.
 */
export default function CapabilityMapShare() {
  const map = useCapabilityMap('shared');
  return (
    <section className="tm-wrap pt-32 pb-56 stack gap-16">
      <div className="row between gap-12 no-print">
        <Link className="tm-link" to="/insights">
          ← Insights
        </Link>
        <button type="button" className="tm-btn btn-primary" onClick={() => window.print()}>
          Print or save as PDF
        </button>
      </div>
      <div>
        <p className="tm-eyebrow">Truminds AI Skill Library</p>
        <PageTitle title="Capability map to share">Capability map</PageTitle>
        <p className="tm-sub">
          Production skills only · aggregates only · {localDate(map.data?.meta.generated_at) ?? ''}
        </p>
      </div>
      {map.isPending ? (
        <Skeleton height={360} />
      ) : map.isError ? (
        <ErrorState error={map.error} />
      ) : (
        <>
          <div className="grid g-200">
            <StatTile
              label="Production skills"
              value={count(map.data.data.totals.production_skills)}
            />
            <StatTile
              label="Evidence-backed cells"
              value={count(map.data.data.totals.evidence_backed_cells)}
              sub={`of ${map.data.data.totals.cells_with_skills} cells with skills`}
            />
            <StatTile label="Runs" value={count(map.data.data.totals.runs)} />
            <StatTile
              label="First-try pass rate"
              value={percent(map.data.data.totals.first_try_pass)}
              tone="pass"
            />
            <StatTile
              label="Client systems served"
              value={count(map.data.data.totals.systems_served)}
            />
          </div>
          {map.data.data.rows.length === 0 ? (
            <EmptyState title="No production skills yet">
              The map fills in as skills reach production.
            </EmptyState>
          ) : (
            <CapabilityMapTable map={map.data.data} />
          )}
        </>
      )}
    </section>
  );
}

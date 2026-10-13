import { Link } from 'react-router-dom';
import { PageTitle } from '../components/Heading';

/**
 * Pod builder (board PodBuilder; SDD-09 §4.11). Release 1 ships this static notice only: X-04 forbids
 * the builder UI in Release 1 (SDD-10 O-05). No API call.
 */
export default function PodBuilder() {
  return (
    <>
      <div className="band-amber">
        <div className="tm-wrap" style={{ paddingTop: 12, paddingBottom: 12, fontSize: 14 }}>
          <strong>Phase 3 preview, not in Release 1.</strong> The pod builder is not part of Release
          1.
        </div>
      </div>
      <section className="tm-wrap pt-32 pb-56">
        <Link className="tm-link" to="/pods">
          ← All pods
        </Link>
        <PageTitle title="Build a pod" className="page-h1 mt-12">
          Build a pod
        </PageTitle>
        <p className="tm-sub">
          The builder will let you pick the AI agents a client engagement needs and show the
          workflows, skills and human roles that come with them. It is planned for Phase 3, after
          Release 1 usage data shows which combinations work. Until then, choose one of the
          ready-made pods.
        </p>
        <Link className="tm-btn btn-primary mt-20" to="/pods">
          Back to pods
        </Link>
      </section>
    </>
  );
}

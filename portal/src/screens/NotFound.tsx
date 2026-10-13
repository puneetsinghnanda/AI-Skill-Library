import { Link } from 'react-router-dom';
import { PageTitle } from '../components/Heading';

export default function NotFound() {
  return (
    <section className="tm-wrap pt-48 pb-56">
      <PageTitle title="Not found">Page not found</PageTitle>
      <p className="tm-sub">This page does not exist, or it is outside what your role can see.</p>
      <Link className="tm-btn btn-primary mt-16" to="/">
        Go to Home
      </Link>
    </section>
  );
}

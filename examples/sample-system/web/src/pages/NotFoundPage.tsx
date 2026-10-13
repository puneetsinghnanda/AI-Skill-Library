import { Link } from 'react-router-dom';

export function NotFoundPage() {
  return (
    <>
      <h1>Page not found</h1>
      <Link to="/orders">Back to order history</Link>
    </>
  );
}

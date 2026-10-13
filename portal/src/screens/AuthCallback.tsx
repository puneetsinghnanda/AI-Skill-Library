import { Link } from 'react-router-dom';

/** MSAL redirect target (SDD-09 §3.3). Sign-in finishes before the router starts (auth/msal.tsx). */
export function AuthCallback() {
  return (
    <main id="main" className="tm-wrap pt-48">
      <h1 className="page-h1">Signing you in</h1>
      <p className="tm-sub" role="status">
        Finishing sign-in with your company account.
      </p>
      <Link to="/" className="tm-btn btn-ghost mt-16">
        Continue to the portal
      </Link>
    </main>
  );
}

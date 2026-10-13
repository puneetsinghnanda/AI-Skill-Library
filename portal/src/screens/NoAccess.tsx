import type { ReactNode } from 'react';
import { useAuth } from '../auth/port';

/** A signed-in user with no active grant sees this and nothing else (SDD-09 §3.3). */
export function NoAccess({ banner }: { banner?: ReactNode }) {
  const auth = useAuth();
  return (
    <>
      {banner}
      <main id="main" className="tm-wrap pt-48">
        <h1 className="page-h1" tabIndex={-1}>
          You do not have access yet. Ask an admin.
        </h1>
        <p className="tm-sub">
          Your company account is signed in, but it has no role in the AI Skill Library yet. Your
          manager can request access through the IT access process.
        </p>
        <button
          type="button"
          className="tm-btn btn-ghost mt-16"
          onClick={() => void auth.signOut()}
        >
          Sign out
        </button>
      </main>
    </>
  );
}

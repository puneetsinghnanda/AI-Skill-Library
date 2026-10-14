import { Link } from 'react-router-dom';
import { ADMIN_NAV, AdminPage } from './parts';

const WHAT: Record<string, string> = {
  '/admin/clients':
    'Create a client (its name is encrypted and added to the deny-list) and record or withdraw its consent.',
  '/admin/projects': 'Create projects under a client and systems with their product repos.',
  '/admin/roles':
    'See every grant, active and revoked. Grant a role at a scope, within the user’s Entra app roles. Revoke a grant with a reason.',
  '/admin/users':
    'See users and their keys. Deactivate a user (keys and grants are revoked) or revoke one signing key with a reason.',
};

/** Admin overview (SDD-09 §4.16, SDD-13 §7.2). No API call. */
export default function AdminHome() {
  return (
    <AdminPage
      title="Administration"
      sub="Set up clients, projects and systems, and manage who can do what. Only the Admin app role sees these screens."
    >
      <ul className="plain-list grid g-220">
        {ADMIN_NAV.filter((n) => n.to !== '/admin').map((n) => (
          <li key={n.to}>
            <Link to={n.to} className="tm-card card-link" style={{ padding: 18 }}>
              <span className="strong">{n.label}</span>
              <span className="small text-2">{WHAT[n.to]}</span>
            </Link>
          </li>
        ))}
      </ul>
      <div className="tm-card soft mt-24" style={{ padding: 18 }}>
        <p className="m-0 strong">Before you start</p>
        <ul className="small text-2">
          <li>
            Your browser asks the service for admin permission (scope{' '}
            <span className="mono">Portal.Write</span>) only when you submit an action here.
          </li>
          <li>Destructive actions ask you to confirm first. None of them can be undone here.</li>
          <li>
            You cannot grant a role to yourself. Each screen lists what exists (clients, projects,
            systems, grants, users and their keys); revoke and deactivate from a row.
          </li>
        </ul>
      </div>
    </AdminPage>
  );
}

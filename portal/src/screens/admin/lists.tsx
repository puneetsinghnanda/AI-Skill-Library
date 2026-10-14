/**
 * Admin lists (SDD-09 §4.16 "Lists", SDD-13 §5.3 and §7.2): tables over the `GET /v1/admin/...`
 * routes, with per-row actions (revoke grant, revoke key, deactivate user) that open the same
 * confirmation dialog as the forms. Lists use the `Portal.Read` token; only the confirmed action
 * asks for `Portal.Write`. Codes and pseudonyms only: these screens never request names.
 */
import { useRef, useState, type ReactNode } from 'react';
import {
  ADMIN_KEY_REASONS,
  ROLE_LABELS,
  admin,
  useAdminAction,
  useAdminClients,
  useAdminGrants,
  useAdminKeys,
  useAdminProjects,
  useAdminSystems,
  useAdminUsers,
  type GrantRole,
  type KeyRevokeReason,
} from '../../api/admin';
import type {
  AdminGrantRow,
  AdminKeyRow,
  AdminUserRow,
  ConsentStatus,
  PagedEnvelope,
} from '../../api/types';
import { useView } from '../../app/ViewContext';
import { ConfirmDialog } from '../../components/ConfirmDialog';
import { StatusBadge } from '../../components/StatusBadge';
import { EmptyState, ErrorState, Skeleton } from '../../components/States';
import { TableRegion } from '../../components/TableRegion';
import { localDate } from '../../lib/format';
import type { StatusWord } from '../../lib/status';
import { ActionError, FormCard, Result, SelectField, TextField } from './parts';

/* ------------------------------------------------------------------ shared table */
interface ListQuery<T> {
  data: { pages: PagedEnvelope<T>[] } | undefined;
  error: unknown;
  isPending: boolean;
  isError: boolean;
  refetch: () => unknown;
  hasNextPage: boolean;
  fetchNextPage: () => unknown;
  isFetchingNextPage: boolean;
}

function ListTable<T>({
  label,
  query,
  head,
  row,
  empty,
  minWidth = 640,
}: {
  label: string;
  query: ListQuery<T>;
  head: string[];
  row: (item: T) => ReactNode;
  empty: string;
  minWidth?: number;
}) {
  if (query.isPending) return <Skeleton height={120} label={`Loading ${label.toLowerCase()}`} />;
  if (query.isError || !query.data)
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  const items = query.data.pages.flatMap((p) => p.data.items);
  if (!items.length) return <EmptyState title={empty} />;
  return (
    <>
      <TableRegion label={label} minWidth={minWidth}>
        <thead>
          <tr>
            {head.map((h) => (
              <th key={h} scope="col">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{items.map(row)}</tbody>
      </TableRegion>
      {query.hasNextPage ? (
        <button
          type="button"
          className="tm-btn btn-ghost mt-12"
          onClick={() => void query.fetchNextPage()}
          disabled={query.isFetchingNextPage}
        >
          {query.isFetchingNextPage ? 'Loading more…' : 'Show more'}
        </button>
      ) : null}
    </>
  );
}

function ListCard({ title, id, children }: { title: string; id: string; children: ReactNode }) {
  return (
    <div className="mt-24">
      <FormCard title={title} id={id}>
        {children}
      </FormCard>
    </div>
  );
}

const when = (iso: string | null | undefined) => (iso ? (localDate(iso) ?? iso) : '—');
const roleLabel = (r: string) => ROLE_LABELS[r as GrantRole] ?? r;

const CONSENT_WORD: Record<ConsentStatus, StatusWord> = {
  recorded: { tone: 'pass', word: 'Recorded' },
  withdrawn: { tone: 'abort', word: 'Withdrawn' },
  none: { tone: 'retry', word: 'Not recorded' },
};
const GRANT_WORD: Record<AdminGrantRow['status'], StatusWord> = {
  active: { tone: 'pass', word: 'Active' },
  revoked: { tone: 'abort', word: 'Revoked' },
};
const KEY_WORD: Record<AdminKeyRow['status'], StatusWord> = {
  active: { tone: 'pass', word: 'Active' },
  revoked: { tone: 'abort', word: 'Revoked' },
  expired: { tone: 'retry', word: 'Expired' },
};
const USER_WORD = (active: boolean): StatusWord =>
  active ? { tone: 'pass', word: 'Active' } : { tone: 'abort', word: 'Inactive' };

function reasonError(v: string): string | undefined {
  return !v.trim() || v.trim().length > 200 ? 'Give a reason (up to 200 characters).' : undefined;
}

/** Moves focus to the dialog's invalid field after a refused confirm. */
function focusInvalid(root: HTMLElement | null) {
  requestAnimationFrame(() =>
    root?.ownerDocument
      .querySelector<HTMLElement>('[role="alertdialog"] [aria-invalid="true"]')
      ?.focus(),
  );
}

/* ------------------------------------------------------------------ clients, projects, systems */
export function ClientsList() {
  const [consent, setConsent] = useState<ConsentStatus | 'all'>('all');
  const q = useAdminClients(consent === 'all' ? {} : { consent });
  return (
    <ListCard title="Clients" id="list-clients">
      <SelectField
        id="list-clients-consent"
        label="Consent"
        value={consent}
        options={[
          { value: 'all', label: 'All clients' },
          { value: 'recorded', label: 'Recorded' },
          { value: 'withdrawn', label: 'Withdrawn' },
          { value: 'none', label: 'Not recorded' },
        ]}
        onChange={setConsent}
      />
      <div className="mt-12">
        <ListTable
          label="Client list"
          query={q}
          head={['Code', 'Consent', 'Reference', 'Scopes', 'Recorded', 'Projects']}
          empty="No clients match."
          row={(c) => (
            <tr key={c.code}>
              <td className="mono">{c.code}</td>
              <td>
                <StatusBadge status={CONSENT_WORD[c.consent.status]} />
              </td>
              <td className="mono">{c.consent.ref ?? '—'}</td>
              <td className="small">{c.consent.scope.join(', ') || '—'}</td>
              <td>{when(c.consent.recorded_at)}</td>
              <td>{c.projects}</td>
            </tr>
          )}
        />
      </div>
    </ListCard>
  );
}

export function ProjectsList() {
  const q = useAdminProjects();
  return (
    <ListCard title="Projects" id="list-projects">
      <ListTable
        label="Project list"
        query={q}
        head={['Code', 'Client', 'Systems']}
        empty="No projects yet."
        minWidth={420}
        row={(p) => (
          <tr key={p.code}>
            <td className="mono">{p.code}</td>
            <td className="mono">{p.client}</td>
            <td>{p.systems}</td>
          </tr>
        )}
      />
    </ListCard>
  );
}

export function SystemsList() {
  const q = useAdminSystems();
  return (
    <ListCard title="Systems" id="list-systems">
      <ListTable
        label="System list"
        query={q}
        head={['Code', 'Project', 'Client', 'Domain', 'Companion repo', 'Product repos']}
        empty="No systems yet."
        minWidth={760}
        row={(s) => (
          <tr key={s.code}>
            <td className="mono">{s.code}</td>
            <td className="mono">{s.project}</td>
            <td className="mono">{s.client}</td>
            <td>{s.domain}</td>
            <td className="mono small">{s.companion_repo}</td>
            <td className="mono small">
              {s.product_repos.map((r) => r.github_full_name).join(', ') || '—'}
            </td>
          </tr>
        )}
      />
    </ListCard>
  );
}

/* ------------------------------------------------------------------ role grants */
export function GrantsList() {
  const [status, setStatus] = useState<'all' | 'active' | 'revoked'>('all');
  const q = useAdminGrants({ status });
  const [target, setTarget] = useState<AdminGrantRow | null>(null);
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | undefined>();
  const box = useRef<HTMLDivElement>(null);
  const m = useAdminAction(admin.revokeGrant);

  function open(g: AdminGrantRow) {
    m.reset();
    setReason('');
    setError(undefined);
    setTarget(g);
  }
  function confirm() {
    if (!target) return;
    const e = reasonError(reason);
    setError(e);
    if (e) return focusInvalid(box.current);
    m.mutate(
      { grantId: target.id, body: { reason: reason.trim() } },
      { onSettled: () => setTarget(null) },
    );
  }

  return (
    <div ref={box}>
      <ListCard title="All role grants" id="list-grants">
        <SelectField
          id="list-grants-status"
          label="Show"
          value={status}
          options={[
            { value: 'all', label: 'Active and revoked' },
            { value: 'active', label: 'Active only' },
            { value: 'revoked', label: 'Revoked only' },
          ]}
          onChange={setStatus}
        />
        <div className="mt-12">
          <ListTable
            label="Grant list"
            query={q}
            head={['User', 'Role', 'Applies to', 'Status', 'Granted', 'Grant id', 'Actions']}
            empty="No grants match."
            minWidth={820}
            row={(g) => (
              <tr key={g.id}>
                <td className="mono">{g.user}</td>
                <td>{roleLabel(g.role)}</td>
                <td>
                  {g.scope_type === 'org' ? (
                    'Whole organisation'
                  ) : (
                    <>
                      {g.scope_type} <span className="mono">{g.scope ?? '—'}</span>
                    </>
                  )}
                </td>
                <td>
                  <StatusBadge status={GRANT_WORD[g.status]} />
                </td>
                <td>{when(g.granted_at)}</td>
                <td className="mono xsmall">{g.id}</td>
                <td>
                  {g.status === 'active' ? (
                    <button
                      type="button"
                      className="tm-btn btn-danger"
                      aria-label={`Revoke grant ${roleLabel(g.role)} for ${g.user}`}
                      onClick={() => open(g)}
                    >
                      Revoke…
                    </button>
                  ) : (
                    '—'
                  )}
                </td>
              </tr>
            )}
          />
        </div>
        <ConfirmDialog
          open={target !== null}
          title="Revoke this role grant?"
          confirmLabel="Revoke grant"
          busy={m.isPending}
          onCancel={() => setTarget(null)}
          onConfirm={confirm}
        >
          <p className="m-0">
            {target ? roleLabel(target.role) : ''} for <span className="mono">{target?.user}</span>{' '}
            (grant <span className="mono">{target?.id}</span>) stops working on the next request.
            The user keeps their other grants.
          </p>
          <TextField
            id="row-grant-reason"
            label="Reason"
            value={reason}
            onChange={setReason}
            error={error}
            multiline
          />
        </ConfirmDialog>
        {m.isSuccess ? (
          <Result>
            <p className="m-0">
              Grant <span className="mono">{m.data.id}</span> revoked.
            </p>
          </Result>
        ) : null}
        {m.isError ? <ActionError error={m.error} /> : null}
      </ListCard>
    </div>
  );
}

/* ------------------------------------------------------------------ users and keys */
function KeysList({ pseudonym }: { pseudonym: string }) {
  const q = useAdminKeys(pseudonym, {});
  const [target, setTarget] = useState<AdminKeyRow | null>(null);
  const [reason, setReason] = useState<KeyRevokeReason | ''>('');
  const [error, setError] = useState<string | undefined>();
  const box = useRef<HTMLDivElement>(null);
  const m = useAdminAction(admin.revokeKey);

  function open(k: AdminKeyRow) {
    m.reset();
    setReason('');
    setError(undefined);
    setTarget(k);
  }
  function confirm() {
    if (!target) return;
    if (!reason) {
      setError('Choose a reason.');
      return focusInvalid(box.current);
    }
    m.mutate({ keyId: target.key_id, body: { reason } }, { onSettled: () => setTarget(null) });
  }

  return (
    <div ref={box}>
      <ListCard title={`Keys of ${pseudonym}`} id="list-keys">
        <ListTable
          label={`Key list of ${pseudonym}`}
          query={q}
          head={['Key id', 'Device', 'Status', 'Expires', 'Actions']}
          empty="This user has no signing keys."
          row={(k) => (
            <tr key={k.key_id}>
              <td className="mono small">{k.key_id}</td>
              <td>{k.device_label ?? '—'}</td>
              <td>
                <StatusBadge status={KEY_WORD[k.status]} suffix={k.revoked_reason ?? undefined} />
              </td>
              <td>{when(k.expires_at)}</td>
              <td>
                {k.status === 'active' ? (
                  <button
                    type="button"
                    className="tm-btn btn-danger"
                    aria-label={`Revoke key ${k.key_id}`}
                    onClick={() => open(k)}
                  >
                    Revoke…
                  </button>
                ) : (
                  '—'
                )}
              </td>
            </tr>
          )}
        />
        <ConfirmDialog
          open={target !== null}
          title={`Revoke key ${target?.key_id ?? ''}?`}
          confirmLabel="Revoke key"
          busy={m.isPending}
          onCancel={() => setTarget(null)}
          onConfirm={confirm}
        >
          <p className="m-0">
            The key can no longer sign. The owner must register a new key with{' '}
            <span className="mono">tsl login</span>. For a lost or compromised key, what it signed
            since it was created is marked untrusted; use the form to give an earlier time.
          </p>
          <SelectField
            id="row-key-reason"
            label="Reason"
            value={reason}
            options={ADMIN_KEY_REASONS}
            onChange={setReason}
            error={error}
          />
        </ConfirmDialog>
        {m.isSuccess ? (
          <Result>
            <p className="m-0">
              Key <span className="mono">{m.data.key_id}</span> revoked ({m.data.revoked_reason}).
            </p>
          </Result>
        ) : null}
        {m.isError ? <ActionError error={m.error} /> : null}
      </ListCard>
    </div>
  );
}

export function UsersList() {
  const { me } = useView();
  const [show, setShow] = useState<'all' | 'active' | 'inactive'>('all');
  const q = useAdminUsers(show === 'all' ? {} : { active: show === 'active' });
  const [keysOf, setKeysOf] = useState<string | null>(null);
  const [target, setTarget] = useState<AdminUserRow | null>(null);
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | undefined>();
  const box = useRef<HTMLDivElement>(null);
  const m = useAdminAction(admin.deactivateUser);

  function open(u: AdminUserRow) {
    m.reset();
    setReason('');
    setError(undefined);
    setTarget(u);
  }
  function confirm() {
    if (!target) return;
    const e = reasonError(reason);
    setError(e);
    if (e) return focusInvalid(box.current);
    m.mutate(
      { pseudonym: target.pseudonym, body: { reason: reason.trim() } },
      { onSettled: () => setTarget(null) },
    );
  }

  return (
    <div ref={box}>
      <ListCard title="Users" id="list-users">
        <SelectField
          id="list-users-active"
          label="Show"
          value={show}
          options={[
            { value: 'all', label: 'All users' },
            { value: 'active', label: 'Active only' },
            { value: 'inactive', label: 'Inactive only' },
          ]}
          onChange={setShow}
        />
        <div className="mt-12">
          <ListTable
            label="User list"
            query={q}
            head={['Pseudonym', 'App roles', 'Roles', 'Status', 'Actions']}
            empty="No users match."
            minWidth={720}
            row={(u) => (
              <tr key={u.pseudonym}>
                <td className="mono">{u.pseudonym}</td>
                <td className="small">{u.app_roles.join(', ') || '—'}</td>
                <td className="small">{u.roles.map(roleLabel).join(', ') || '—'}</td>
                <td>
                  <StatusBadge status={USER_WORD(u.active)} />
                </td>
                <td>
                  <div className="row gap-8">
                    <button
                      type="button"
                      className="tm-btn btn-ghost"
                      aria-label={`Show keys of ${u.pseudonym}`}
                      aria-pressed={keysOf === u.pseudonym}
                      onClick={() => setKeysOf(keysOf === u.pseudonym ? null : u.pseudonym)}
                    >
                      Keys
                    </button>
                    {u.active && u.pseudonym !== me.pseudonym ? (
                      <button
                        type="button"
                        className="tm-btn btn-danger"
                        aria-label={`Deactivate ${u.pseudonym}`}
                        onClick={() => open(u)}
                      >
                        Deactivate…
                      </button>
                    ) : null}
                  </div>
                </td>
              </tr>
            )}
          />
        </div>
        <ConfirmDialog
          open={target !== null}
          title={`Deactivate ${target?.pseudonym ?? ''}?`}
          confirmLabel="Deactivate user"
          busy={m.isPending}
          onCancel={() => setTarget(null)}
          onConfirm={confirm}
        >
          <p className="m-0">
            The user is signed out of the portal and the service. All their signing keys are revoked
            as offboarded and all their role grants are revoked. Work they signed before now stays
            valid.
          </p>
          <TextField
            id="row-deactivate-reason"
            label="Reason"
            value={reason}
            onChange={setReason}
            error={error}
            multiline
          />
        </ConfirmDialog>
        {m.isSuccess ? (
          <Result>
            <p className="m-0">
              <span className="mono">{m.data.pseudonym}</span> deactivated.{' '}
              {m.data.keys_revoked.length} key{m.data.keys_revoked.length === 1 ? '' : 's'} and{' '}
              {m.data.grants_revoked} grant{m.data.grants_revoked === 1 ? '' : 's'} revoked.
            </p>
          </Result>
        ) : null}
        {m.isError ? <ActionError error={m.error} /> : null}
      </ListCard>
      {keysOf ? <KeysList pseudonym={keysOf} /> : null}
    </div>
  );
}

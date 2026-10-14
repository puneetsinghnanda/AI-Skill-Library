/**
 * Shared parts of the admin screens (SDD-09 §4.16): page frame with the admin sub-navigation,
 * labelled form fields with inline errors, result and error panels.
 */
import type { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ApiError } from '../../api/client';
import { PageTitle } from '../../components/Heading';

export const ADMIN_NAV = [
  { to: '/admin', label: 'Overview' },
  { to: '/admin/clients', label: 'Clients and consent' },
  { to: '/admin/projects', label: 'Projects and systems' },
  { to: '/admin/roles', label: 'Role grants' },
  { to: '/admin/users', label: 'Users and keys' },
] as const;

export function AdminPage({
  title,
  sub,
  children,
}: {
  title: string;
  sub: ReactNode;
  children: ReactNode;
}) {
  const { pathname } = useLocation();
  return (
    <section className="tm-wrap pt-32 pb-56">
      <p className="tm-eyebrow">Admin</p>
      <PageTitle title={`${title} · Admin`}>{title}</PageTitle>
      <p className="tm-sub">{sub}</p>
      <nav aria-label="Admin sections" className="admin-subnav">
        {ADMIN_NAV.map((n) => (
          <Link key={n.to} to={n.to} aria-current={pathname === n.to ? 'page' : undefined}>
            {n.label}
          </Link>
        ))}
      </nav>
      <p className="xsmall text-2 mt-12">
        Every action here is checked and written to the audit log by the insights service. Codes
        only: never type a client name except in the client form.
      </p>
      <div className="mt-24">{children}</div>
    </section>
  );
}

export function FormCard({
  title,
  id,
  children,
}: {
  title: string;
  id: string;
  children: ReactNode;
}) {
  return (
    <section className="tm-card" aria-labelledby={id} style={{ padding: 20 }}>
      <h2 className="tm-h2" id={id} style={{ fontSize: 18 }}>
        {title}
      </h2>
      <div className="mt-12">{children}</div>
    </section>
  );
}

export type Errors<K extends string> = Partial<Record<K, string>>;

function describedBy(id: string, hint?: string, error?: string): string | undefined {
  const ids = [hint ? `${id}-hint` : '', error ? `${id}-err` : ''].filter(Boolean);
  return ids.length ? ids.join(' ') : undefined;
}

export function TextField({
  id,
  label,
  value,
  onChange,
  hint,
  error,
  multiline = false,
  required = true,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  hint?: string;
  error?: string;
  multiline?: boolean;
  required?: boolean;
}) {
  const common = {
    id,
    value,
    'aria-invalid': error ? true : undefined,
    'aria-describedby': describedBy(id, hint, error),
    'aria-required': required || undefined,
  } as const;
  return (
    <div className="form-field">
      <label htmlFor={id}>
        {label}
        {required ? null : <span className="text-2"> (optional)</span>}
      </label>
      {hint ? (
        <p className="field-hint" id={`${id}-hint`}>
          {hint}
        </p>
      ) : null}
      {multiline ? (
        <textarea {...common} onChange={(e) => onChange(e.target.value)} />
      ) : (
        <input
          {...common}
          type="text"
          autoComplete="off"
          spellCheck={false}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
      {error ? (
        <p className="field-error" id={`${id}-err`}>
          {error}
        </p>
      ) : null}
    </div>
  );
}

export function SelectField<V extends string>({
  id,
  label,
  value,
  options,
  onChange,
  hint,
  error,
}: {
  id: string;
  label: string;
  value: V | '';
  options: { value: V; label: string }[];
  onChange: (v: V) => void;
  hint?: string;
  error?: string;
}) {
  return (
    <div className="form-field">
      <label htmlFor={id}>{label}</label>
      {hint ? (
        <p className="field-hint" id={`${id}-hint`}>
          {hint}
        </p>
      ) : null}
      <select
        id={id}
        value={value}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, hint, error)}
        onChange={(e) => onChange(e.target.value as V)}
      >
        {value === '' ? <option value="">Choose…</option> : null}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      {error ? (
        <p className="field-error" id={`${id}-err`}>
          {error}
        </p>
      ) : null}
    </div>
  );
}

/** Moves focus to the first field with an error after a failed submit. */
export function focusFirstError(form: HTMLFormElement | null) {
  form?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus();
}

export function SubmitRow({
  label,
  pending,
  danger = false,
}: {
  label: string;
  pending: boolean;
  danger?: boolean;
}) {
  return (
    <div>
      <button
        type="submit"
        className={`tm-btn ${danger ? 'btn-danger' : 'btn-primary'}`}
        disabled={pending}
      >
        {pending ? 'Saving…' : label}
      </button>
    </div>
  );
}

/** Success panel: what the service did, in words, plus the identifiers it returned. */
export function Result({ children }: { children: ReactNode }) {
  return (
    <div className="tm-card result-card mt-12" role="status" style={{ padding: 14 }}>
      {children}
      <p className="xsmall m-0 mt-4">Recorded in the audit log.</p>
    </div>
  );
}

/** Failure panel: the service's error code, its words and the request id (SDD-09 §5.1.4). */
export function ActionError({ error }: { error: unknown }) {
  const e = error instanceof ApiError ? error : null;
  const title =
    e?.code === 'E-ADM-01'
      ? 'You cannot grant a role to yourself. Ask another admin.'
      : e?.status === 401
        ? 'Your session could not get admin permission. Sign in again and retry.'
        : e?.status === 403
          ? 'The service refused this action for your account.'
          : e?.status === 404
            ? 'Not found. Check the code or id.'
            : e?.status === 400
              ? 'The service did not accept these values.'
              : 'The action did not complete.';
  return (
    <div className="tm-card error-card mt-12" role="alert" style={{ padding: 14 }}>
      <p className="m-0 strong">{title}</p>
      {e?.detail ? <p className="body text-2 m-0 mt-4">{e.detail}</p> : null}
      {e ? (
        <p className="xsmall text-2 m-0 mt-4">
          Error <span className="mono">{e.code}</span> · Request id{' '}
          <span className="mono">{e.requestId}</span>
        </p>
      ) : null}
    </div>
  );
}

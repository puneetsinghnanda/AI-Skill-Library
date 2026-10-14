import { useRef, useState, type FormEvent } from 'react';
import {
  CONSENT_SCOPES,
  PATTERNS,
  admin,
  useAdminAction,
  type ConsentScope,
} from '../../api/admin';
import { ConfirmDialog } from '../../components/ConfirmDialog';
import {
  ActionError,
  AdminPage,
  FormCard,
  Result,
  SubmitRow,
  TextField,
  focusFirstError,
  type Errors,
} from './parts';
import { ClientsList } from './lists';

const CODE_HINT = 'CL- and 2 to 8 capital letters or digits, for example CL-ACME2.';

function CreateClient() {
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [aliases, setAliases] = useState('');
  const [errors, setErrors] = useState<Errors<'code' | 'name' | 'aliases'>>({});
  const form = useRef<HTMLFormElement>(null);
  const m = useAdminAction(admin.createClient);

  function submit(e: FormEvent) {
    e.preventDefault();
    const list = aliases
      .split(',')
      .map((a) => a.trim())
      .filter(Boolean);
    const next: typeof errors = {};
    if (!PATTERNS.client.test(code.trim())) next.code = `Enter a client code. ${CODE_HINT}`;
    if (!name.trim() || name.trim().length > 200)
      next.name = 'Enter the client’s display name (up to 200 characters).';
    if (list.length > 20) next.aliases = 'Up to 20 aliases.';
    setErrors(next);
    if (Object.keys(next).length) {
      requestAnimationFrame(() => focusFirstError(form.current));
      return;
    }
    m.mutate({ code: code.trim(), display_name: name.trim(), aliases: list });
  }

  return (
    <FormCard title="Create a client" id="create-client">
      <form ref={form} className="admin-form" noValidate onSubmit={submit}>
        <TextField
          id="client-code"
          label="Client code"
          hint={CODE_HINT}
          value={code}
          onChange={setCode}
          error={errors.code}
        />
        <TextField
          id="client-name"
          label="Display name"
          hint="Stored encrypted. Its words are added to the client deny-list."
          value={name}
          onChange={setName}
          error={errors.name}
        />
        <TextField
          id="client-aliases"
          label="Other names"
          hint="Comma-separated short names or brands, also added to the deny-list."
          value={aliases}
          onChange={setAliases}
          error={errors.aliases}
          required={false}
        />
        <SubmitRow label="Create client" pending={m.isPending} />
      </form>
      {m.isSuccess ? (
        <Result>
          <p className="m-0">
            Client <span className="mono">{m.data.code}</span> created. Deny-list version{' '}
            <span className="mono">{m.data.denylist_version}</span>.
          </p>
        </Result>
      ) : null}
      {m.isError ? <ActionError error={m.error} /> : null}
    </FormCard>
  );
}

function RecordConsent() {
  const [code, setCode] = useState('');
  const [ref, setRef] = useState('');
  const [scope, setScope] = useState<ConsentScope[]>([]);
  const [errors, setErrors] = useState<Errors<'code' | 'ref' | 'scope'>>({});
  const form = useRef<HTMLFormElement>(null);
  const m = useAdminAction(admin.consent);

  function toggle(s: ConsentScope, on: boolean) {
    setScope((prev) => (on ? [...prev, s] : prev.filter((x) => x !== s)));
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    const next: typeof errors = {};
    if (!PATTERNS.client.test(code.trim())) next.code = `Enter a client code. ${CODE_HINT}`;
    if (!PATTERNS.consentRef.test(ref.trim()))
      next.ref = 'Enter the consent reference: 3 to 40 capital letters, digits or hyphens.';
    if (scope.length === 0) next.scope = 'Choose at least one thing the client consented to.';
    setErrors(next);
    if (Object.keys(next).length) {
      requestAnimationFrame(() => focusFirstError(form.current));
      return;
    }
    m.mutate({
      code: code.trim(),
      body: { action: 'record', consent_ref: ref.trim(), scope },
    });
  }

  return (
    <FormCard title="Record consent" id="record-consent">
      <form ref={form} className="admin-form" noValidate onSubmit={submit}>
        <TextField
          id="consent-code"
          label="Client code"
          value={code}
          onChange={setCode}
          error={errors.code}
        />
        <TextField
          id="consent-ref"
          label="Consent reference"
          hint="The id of the signed consent record, for example CONSENT-0042."
          value={ref}
          onChange={setRef}
          error={errors.ref}
        />
        <fieldset
          className="form-field"
          aria-describedby={errors.scope ? 'consent-scope-err' : undefined}
        >
          <legend>Consent covers</legend>
          {CONSENT_SCOPES.map((s) => (
            <label key={s.value} className="toggle">
              <input
                type="checkbox"
                checked={scope.includes(s.value)}
                aria-invalid={errors.scope ? true : undefined}
                onChange={(e) => toggle(s.value, e.target.checked)}
              />
              {s.label}
            </label>
          ))}
          {errors.scope ? (
            <p className="field-error" id="consent-scope-err">
              {errors.scope}
            </p>
          ) : null}
        </fieldset>
        <SubmitRow label="Record consent" pending={m.isPending} />
      </form>
      {m.isSuccess ? (
        <Result>
          <p className="m-0">
            Consent recorded for <span className="mono">{m.data.code}</span>.
          </p>
        </Result>
      ) : null}
      {m.isError ? <ActionError error={m.error} /> : null}
    </FormCard>
  );
}

function WithdrawConsent() {
  const [code, setCode] = useState('');
  const [error, setError] = useState<string | undefined>();
  const [confirming, setConfirming] = useState(false);
  const form = useRef<HTMLFormElement>(null);
  const m = useAdminAction(admin.consent);

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!PATTERNS.client.test(code.trim())) {
      setError(`Enter a client code. ${CODE_HINT}`);
      requestAnimationFrame(() => focusFirstError(form.current));
      return;
    }
    setError(undefined);
    m.reset();
    setConfirming(true);
  }

  return (
    <FormCard title="Withdraw consent" id="withdraw-consent">
      <p className="small text-2 m-0">
        Withdrawal stops new runs for the client’s systems. Recorded consent stays in the audit log.
      </p>
      <form ref={form} className="admin-form mt-12" noValidate onSubmit={submit}>
        <TextField
          id="withdraw-code"
          label="Client code"
          value={code}
          onChange={setCode}
          error={error}
        />
        <SubmitRow label="Withdraw consent…" pending={m.isPending} danger />
      </form>
      <ConfirmDialog
        open={confirming}
        title={`Withdraw consent for ${code.trim()}?`}
        confirmLabel="Withdraw consent"
        busy={m.isPending}
        onCancel={() => setConfirming(false)}
        onConfirm={() =>
          m.mutate(
            { code: code.trim(), body: { action: 'withdraw' } },
            { onSettled: () => setConfirming(false) },
          )
        }
      >
        <p className="m-0">
          The client’s consent is marked withdrawn now. Engineers cannot start runs on its systems
          until consent is recorded again.
        </p>
      </ConfirmDialog>
      {m.isSuccess ? (
        <Result>
          <p className="m-0">
            Consent withdrawn for <span className="mono">{m.data.code}</span>.
          </p>
        </Result>
      ) : null}
      {m.isError ? <ActionError error={m.error} /> : null}
    </FormCard>
  );
}

/** Clients and consent (SDD-13 §7.2; SDD-12 §7). */
export default function AdminClients() {
  return (
    <AdminPage
      title="Clients and consent"
      sub="A client must exist, with consent recorded, before its projects and systems can be used."
    >
      <div className="admin-grid">
        <CreateClient />
        <RecordConsent />
        <WithdrawConsent />
      </div>
      <ClientsList />
    </AdminPage>
  );
}

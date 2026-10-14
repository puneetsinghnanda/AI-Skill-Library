import { useRef, useState, type FormEvent } from 'react';
import {
  ADMIN_KEY_REASONS,
  PATTERNS,
  admin,
  useAdminAction,
  type KeyRevokeReason,
} from '../../api/admin';
import { useView } from '../../app/ViewContext';
import { ConfirmDialog } from '../../components/ConfirmDialog';
import {
  ActionError,
  AdminPage,
  FormCard,
  Result,
  SelectField,
  SubmitRow,
  TextField,
  focusFirstError,
  type Errors,
} from './parts';
import { UsersList } from './lists';

function DeactivateUser() {
  const { me } = useView();
  const [user, setUser] = useState('');
  const [reason, setReason] = useState('');
  const [errors, setErrors] = useState<Errors<'user' | 'reason'>>({});
  const [confirming, setConfirming] = useState(false);
  const form = useRef<HTMLFormElement>(null);
  const m = useAdminAction(admin.deactivateUser);

  function submit(e: FormEvent) {
    e.preventDefault();
    const next: typeof errors = {};
    const u = user.trim();
    if (!PATTERNS.user.test(u)) next.user = 'Enter the user’s pseudonym, like eng-4f2a.';
    else if (u === me.pseudonym) next.user = 'You cannot deactivate yourself here.';
    if (!reason.trim() || reason.trim().length > 200)
      next.reason = 'Give a reason (up to 200 characters).';
    setErrors(next);
    if (Object.keys(next).length) {
      requestAnimationFrame(() => focusFirstError(form.current));
      return;
    }
    m.reset();
    setConfirming(true);
  }

  return (
    <FormCard title="Deactivate a user" id="deactivate-user">
      <p className="small text-2 m-0">
        For people who leave or no longer need access. Also remove them from the Entra app roles.
      </p>
      <form ref={form} className="admin-form mt-12" noValidate onSubmit={submit}>
        <TextField
          id="deactivate-user-id"
          label="User pseudonym"
          value={user}
          onChange={setUser}
          error={errors.user}
        />
        <TextField
          id="deactivate-reason"
          label="Reason"
          value={reason}
          onChange={setReason}
          error={errors.reason}
          multiline
        />
        <SubmitRow label="Deactivate user…" pending={m.isPending} danger />
      </form>
      <ConfirmDialog
        open={confirming}
        title={`Deactivate ${user.trim()}?`}
        confirmLabel="Deactivate user"
        busy={m.isPending}
        onCancel={() => setConfirming(false)}
        onConfirm={() =>
          m.mutate(
            { pseudonym: user.trim(), body: { reason: reason.trim() } },
            { onSettled: () => setConfirming(false) },
          )
        }
      >
        <p className="m-0">
          The user is signed out of the portal and the service. All their signing keys are revoked
          as offboarded and all their role grants are revoked. Work they signed before now stays
          valid.
        </p>
      </ConfirmDialog>
      {m.isSuccess ? (
        <Result>
          <p className="m-0">
            <span className="mono">{m.data.pseudonym}</span> deactivated.{' '}
            {m.data.keys_revoked.length} key{m.data.keys_revoked.length === 1 ? '' : 's'} and{' '}
            {m.data.grants_revoked} grant{m.data.grants_revoked === 1 ? '' : 's'} revoked.
          </p>
          {m.data.keys_revoked.length ? (
            <ul className="small m-0 mt-4">
              {m.data.keys_revoked.map((k) => (
                <li key={k} className="mono">
                  {k}
                </li>
              ))}
            </ul>
          ) : null}
        </Result>
      ) : null}
      {m.isError ? <ActionError error={m.error} /> : null}
    </FormCard>
  );
}

const NEEDS_SINCE: KeyRevokeReason[] = ['lost_device', 'compromised'];

function RevokeKey() {
  const [keyId, setKeyId] = useState('');
  const [reason, setReason] = useState<KeyRevokeReason | ''>('');
  const [since, setSince] = useState('');
  const [note, setNote] = useState('');
  const [errors, setErrors] = useState<Errors<'keyId' | 'reason' | 'since' | 'note'>>({});
  const [confirming, setConfirming] = useState(false);
  const form = useRef<HTMLFormElement>(null);
  const m = useAdminAction(admin.revokeKey);
  const showSince = reason !== '' && NEEDS_SINCE.includes(reason);

  function submit(e: FormEvent) {
    e.preventDefault();
    const next: typeof errors = {};
    if (!PATTERNS.keyId.test(keyId.trim()))
      next.keyId = 'Enter the key id: key_ and 26 capital letters or digits.';
    if (!reason) next.reason = 'Choose a reason.';
    if (showSince && since.trim() && Number.isNaN(Date.parse(since.trim())))
      next.since = 'Enter a date and time like 2026-01-12T09:30:00Z, or leave it empty.';
    if (note.length > 200) next.note = 'Up to 200 characters.';
    setErrors(next);
    if (Object.keys(next).length) {
      requestAnimationFrame(() => focusFirstError(form.current));
      return;
    }
    m.reset();
    setConfirming(true);
  }

  return (
    <FormCard title="Revoke a signing key" id="revoke-key">
      <p className="small text-2 m-0">
        Lost or compromised keys also mark what the key signed after the given time as untrusted
        (SDD-07 §7.3).
      </p>
      <form ref={form} className="admin-form mt-12" noValidate onSubmit={submit}>
        <TextField
          id="revoke-key-id"
          label="Key id"
          value={keyId}
          onChange={setKeyId}
          error={errors.keyId}
        />
        <SelectField
          id="revoke-key-reason"
          label="Reason"
          value={reason}
          options={ADMIN_KEY_REASONS}
          onChange={setReason}
          error={errors.reason}
        />
        {showSince ? (
          <TextField
            id="revoke-key-since"
            label="Compromised since"
            hint="Empty means since the key was created."
            value={since}
            onChange={setSince}
            error={errors.since}
            required={false}
          />
        ) : null}
        <TextField
          id="revoke-key-note"
          label="Note"
          value={note}
          onChange={setNote}
          error={errors.note}
          multiline
          required={false}
        />
        <SubmitRow label="Revoke key…" pending={m.isPending} danger />
      </form>
      <ConfirmDialog
        open={confirming}
        title={`Revoke key ${keyId.trim()}?`}
        confirmLabel="Revoke key"
        busy={m.isPending}
        onCancel={() => setConfirming(false)}
        onConfirm={() =>
          m.mutate(
            {
              keyId: keyId.trim(),
              body: {
                reason: reason as KeyRevokeReason,
                ...(showSince && since.trim() ? { compromised_since: since.trim() } : {}),
                ...(note.trim() ? { note: note.trim() } : {}),
              },
            },
            { onSettled: () => setConfirming(false) },
          )
        }
      >
        <p className="m-0">
          The key can no longer sign. The owner must register a new key with{' '}
          <span className="mono">tsl login</span>.
        </p>
      </ConfirmDialog>
      {m.isSuccess ? (
        <Result>
          <p className="m-0">
            Key <span className="mono">{m.data.key_id}</span> revoked ({m.data.revoked_reason}).
          </p>
        </Result>
      ) : null}
      {m.isError ? <ActionError error={m.error} /> : null}
    </FormCard>
  );
}

/** Users and keys (SDD-13 §7.2, §9; SDD-07 §5.6). */
export default function AdminUsers() {
  return (
    <AdminPage
      title="Users and keys"
      sub="Offboarding and key revocation. Both take effect on the next request and cannot be undone here."
    >
      <div className="admin-grid">
        <DeactivateUser />
        <RevokeKey />
      </div>
      <UsersList />
    </AdminPage>
  );
}

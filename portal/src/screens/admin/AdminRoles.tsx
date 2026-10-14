import { useRef, useState, type FormEvent } from 'react';
import {
  PATTERNS,
  ROLE_LABELS,
  ROLE_SCOPES,
  STAGES,
  admin,
  useAdminAction,
  type GrantRole,
  type ScopeType,
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
import { GrantsList } from './lists';

const SCOPE_LABELS: Record<ScopeType, string> = {
  org: 'Whole organisation',
  client: 'Client',
  project: 'Project',
  system: 'System',
  skill: 'Skill',
  stage: 'Stage',
};

const SCOPE_HINTS: Partial<Record<ScopeType, string>> = {
  client: 'Client code, like CL-ACME2.',
  project: 'Project code, like PRJ-12.',
  system: 'System code, like SYS-ORDERS.',
  skill: 'Skill id, like threat-model.',
};

const ROLES = (Object.keys(ROLE_LABELS) as GrantRole[]).map((r) => ({
  value: r,
  label: ROLE_LABELS[r],
}));

function scopeError(type: ScopeType, scope: string): string | undefined {
  if (type === 'org') return undefined;
  const v = scope.trim();
  if (!v) return 'Enter the scope.';
  if (type === 'client' && !PATTERNS.client.test(v)) return 'Enter a client code, like CL-ACME2.';
  if (type === 'project' && !PATTERNS.project.test(v)) return 'Enter a project code, like PRJ-12.';
  if (type === 'system' && !PATTERNS.system.test(v)) return 'Enter a system code, like SYS-ORDERS.';
  if (v.length > 60) return 'Up to 60 characters.';
  return undefined;
}

function GrantRoleForm() {
  const { me } = useView();
  const [user, setUser] = useState('');
  const [role, setRole] = useState<GrantRole | ''>('');
  const [scopeType, setScopeType] = useState<ScopeType | ''>('');
  const [scope, setScope] = useState('');
  const [errors, setErrors] = useState<Errors<'user' | 'role' | 'scopeType' | 'scope'>>({});
  const form = useRef<HTMLFormElement>(null);
  const m = useAdminAction(admin.grantRole);

  const allowed = role ? ROLE_SCOPES[role] : [];

  function chooseRole(r: GrantRole) {
    setRole(r);
    const types = ROLE_SCOPES[r];
    setScopeType(types.length === 1 ? (types[0] ?? '') : '');
    setScope('');
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    const next: typeof errors = {};
    const u = user.trim();
    if (!PATTERNS.user.test(u)) next.user = 'Enter the user’s pseudonym, like eng-4f2a.';
    else if (u === me.pseudonym) next.user = 'You cannot grant a role to yourself.';
    if (!role) next.role = 'Choose a role.';
    if (!scopeType) next.scopeType = 'Choose where the role applies.';
    else if (role && !ROLE_SCOPES[role].includes(scopeType))
      next.scopeType = `${ROLE_LABELS[role]} cannot be granted at this scope.`;
    if (scopeType) {
      const se = scopeError(scopeType, scope);
      if (se) next.scope = se;
    }
    setErrors(next);
    if (Object.keys(next).length || !role || !scopeType) {
      requestAnimationFrame(() => focusFirstError(form.current));
      return;
    }
    m.mutate({
      user: u,
      role,
      scope_type: scopeType,
      scope: scopeType === 'org' ? null : scope.trim(),
    });
  }

  return (
    <FormCard title="Grant a role" id="grant-role">
      <form ref={form} className="admin-form" noValidate onSubmit={submit}>
        <TextField
          id="grant-user"
          label="User pseudonym"
          hint="The user must have signed in once and hold an Entra app role that allows the role."
          value={user}
          onChange={setUser}
          error={errors.user}
        />
        <SelectField
          id="grant-role-select"
          label="Role"
          value={role}
          options={ROLES}
          onChange={chooseRole}
          error={errors.role}
        />
        <SelectField
          id="grant-scope-type"
          label="Applies to"
          value={scopeType}
          options={allowed.map((t) => ({ value: t, label: SCOPE_LABELS[t] }))}
          onChange={(t) => {
            setScopeType(t);
            setScope('');
          }}
          error={errors.scopeType}
          hint={role ? undefined : 'Choose a role first.'}
        />
        {scopeType === 'stage' ? (
          <SelectField
            id="grant-scope"
            label="Stage"
            value={scope as (typeof STAGES)[number] | ''}
            options={STAGES.map((s) => ({ value: s, label: s }))}
            onChange={setScope}
            error={errors.scope}
          />
        ) : scopeType && scopeType !== 'org' ? (
          <TextField
            id="grant-scope"
            label={SCOPE_LABELS[scopeType]}
            hint={SCOPE_HINTS[scopeType]}
            value={scope}
            onChange={setScope}
            error={errors.scope}
          />
        ) : null}
        <SubmitRow label="Grant role" pending={m.isPending} />
      </form>
      {m.isSuccess ? (
        <Result>
          <p className="m-0">
            {ROLE_LABELS[m.data.role]} granted to <span className="mono">{m.data.user}</span>
            {m.data.scope ? (
              <>
                {' '}
                on <span className="mono">{m.data.scope}</span>
              </>
            ) : null}
            . Grant id <span className="mono">{m.data.id}</span>.
          </p>
          {m.data.role === 'engineer' || m.data.role === 'tech_lead' ? (
            <p className="small m-0 mt-4">
              Next: add the user to the system’s GitHub team by hand (SDD-13 §7.3).
            </p>
          ) : null}
        </Result>
      ) : null}
      {m.isError ? <ActionError error={m.error} /> : null}
    </FormCard>
  );
}

function RevokeGrant() {
  const [grantId, setGrantId] = useState('');
  const [reason, setReason] = useState('');
  const [errors, setErrors] = useState<Errors<'grantId' | 'reason'>>({});
  const [confirming, setConfirming] = useState(false);
  const form = useRef<HTMLFormElement>(null);
  const m = useAdminAction(admin.revokeGrant);

  function submit(e: FormEvent) {
    e.preventDefault();
    const next: typeof errors = {};
    if (!PATTERNS.grantId.test(grantId.trim()))
      next.grantId = 'Enter the grant id (36 characters, from the grant list or result).';
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
    <FormCard title="Revoke a role grant" id="revoke-grant">
      <form ref={form} className="admin-form" noValidate onSubmit={submit}>
        <TextField
          id="revoke-grant-id"
          label="Grant id"
          value={grantId}
          onChange={setGrantId}
          error={errors.grantId}
        />
        <TextField
          id="revoke-grant-reason"
          label="Reason"
          value={reason}
          onChange={setReason}
          error={errors.reason}
          multiline
        />
        <SubmitRow label="Revoke grant…" pending={m.isPending} danger />
      </form>
      <ConfirmDialog
        open={confirming}
        title="Revoke this role grant?"
        confirmLabel="Revoke grant"
        busy={m.isPending}
        onCancel={() => setConfirming(false)}
        onConfirm={() =>
          m.mutate(
            { grantId: grantId.trim(), body: { reason: reason.trim() } },
            { onSettled: () => setConfirming(false) },
          )
        }
      >
        <p className="m-0">
          Grant <span className="mono">{grantId.trim()}</span> stops working on the next request.
          The user keeps their other grants.
        </p>
      </ConfirmDialog>
      {m.isSuccess ? (
        <Result>
          <p className="m-0">
            Grant <span className="mono">{m.data.id}</span> revoked.
          </p>
        </Result>
      ) : null}
      {m.isError ? <ActionError error={m.error} /> : null}
    </FormCard>
  );
}

/** Role grants (SDD-13 §7.2; SDD-07 §3.3 ceiling; E-ADM-01 no self-grant). */
export default function AdminRoles() {
  return (
    <AdminPage
      title="Role grants"
      sub="Roles decide what each person sees and approves. A role can never exceed the person’s Entra app roles."
    >
      <div className="admin-grid">
        <GrantRoleForm />
        <RevokeGrant />
      </div>
      <GrantsList />
    </AdminPage>
  );
}

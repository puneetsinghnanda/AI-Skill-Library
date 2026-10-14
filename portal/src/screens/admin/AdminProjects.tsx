import { useRef, useState, type FormEvent } from 'react';
import { PATTERNS, admin, useAdminAction, type RepoIn } from '../../api/admin';
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
import { ProjectsList, SystemsList } from './lists';

function CreateProject() {
  const [client, setClient] = useState('');
  const [code, setCode] = useState('');
  const [errors, setErrors] = useState<Errors<'client' | 'code'>>({});
  const form = useRef<HTMLFormElement>(null);
  const m = useAdminAction(admin.createProject);

  function submit(e: FormEvent) {
    e.preventDefault();
    const next: typeof errors = {};
    if (!PATTERNS.client.test(client.trim())) next.client = 'Enter a client code, like CL-ACME2.';
    if (!PATTERNS.project.test(code.trim()))
      next.code = 'Enter a project code: PRJ- and 2 to 8 capital letters or digits.';
    setErrors(next);
    if (Object.keys(next).length) {
      requestAnimationFrame(() => focusFirstError(form.current));
      return;
    }
    m.mutate({ client: client.trim(), code: code.trim() });
  }

  return (
    <FormCard title="Create a project" id="create-project">
      <form ref={form} className="admin-form" noValidate onSubmit={submit}>
        <TextField
          id="project-client"
          label="Client code"
          value={client}
          onChange={setClient}
          error={errors.client}
        />
        <TextField
          id="project-code"
          label="Project code"
          hint="For example PRJ-12."
          value={code}
          onChange={setCode}
          error={errors.code}
        />
        <SubmitRow label="Create project" pending={m.isPending} />
      </form>
      {m.isSuccess ? (
        <Result>
          <p className="m-0">
            Project <span className="mono">{m.data.code}</span> created under{' '}
            <span className="mono">{m.data.client}</span>.
          </p>
        </Result>
      ) : null}
      {m.isError ? <ActionError error={m.error} /> : null}
    </FormCard>
  );
}

type RepoRow = RepoIn & { key: number };
type SysField = 'project' | 'code' | 'domain' | 'companion' | `repo-${number}`;

const KINDS: { value: NonNullable<RepoIn['kind']>; label: string }[] = [
  { value: 'product', label: 'Product (pull requests allowed)' },
  { value: 'read_only', label: 'Read only' },
];

function CreateSystem() {
  const [project, setProject] = useState('');
  const [code, setCode] = useState('');
  const [domain, setDomain] = useState('');
  const [companion, setCompanion] = useState('');
  const [repos, setRepos] = useState<RepoRow[]>([]);
  const [errors, setErrors] = useState<Errors<SysField>>({});
  const nextKey = useRef(1);
  const form = useRef<HTMLFormElement>(null);
  const m = useAdminAction(admin.createSystem);

  function update(key: number, patch: Partial<RepoIn>) {
    setRepos((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    const next: typeof errors = {};
    if (!PATTERNS.project.test(project.trim())) next.project = 'Enter a project code, like PRJ-12.';
    if (!PATTERNS.system.test(code.trim()))
      next.code = 'Enter a system code: SYS- and 2 to 8 capital letters or digits.';
    if (!PATTERNS.domain.test(domain.trim()))
      next.domain =
        'Enter a domain: lower-case letters, digits and hyphens, starting with a letter.';
    if (!PATTERNS.repo.test(companion.trim()))
      next.companion = 'Enter the companion repo as org/repo.';
    repos.forEach((r) => {
      if (!PATTERNS.repoName.test(r.name.trim()) || !PATTERNS.repo.test(r.github_full_name.trim()))
        next[`repo-${r.key}`] =
          'Each repo needs a short name (lower case, digits, hyphens) and org/repo.';
    });
    if (repos.length > 20) next.companion = 'Up to 20 product repos.';
    setErrors(next);
    if (Object.keys(next).length) {
      requestAnimationFrame(() => focusFirstError(form.current));
      return;
    }
    m.mutate({
      project: project.trim(),
      code: code.trim(),
      domain: domain.trim(),
      companion_repo: companion.trim(),
      product_repos: repos.map((r) => ({
        name: r.name.trim(),
        github_full_name: r.github_full_name.trim(),
        kind: r.kind ?? 'product',
      })),
    });
  }

  return (
    <FormCard title="Create a system" id="create-system">
      <form ref={form} className="admin-form" noValidate onSubmit={submit}>
        <TextField
          id="system-project"
          label="Project code"
          value={project}
          onChange={setProject}
          error={errors.project}
        />
        <TextField
          id="system-code"
          label="System code"
          hint="For example SYS-ORDERS."
          value={code}
          onChange={setCode}
          error={errors.code}
        />
        <TextField
          id="system-domain"
          label="Domain"
          hint="For example digital or embedded."
          value={domain}
          onChange={setDomain}
          error={errors.domain}
        />
        <TextField
          id="system-companion"
          label="Companion repo"
          hint="org/repo of the system’s companion repo."
          value={companion}
          onChange={setCompanion}
          error={errors.companion}
        />
        <fieldset className="form-field">
          <legend>Product repos</legend>
          {repos.length === 0 ? <p className="field-hint">No product repos yet.</p> : null}
          {repos.map((r, i) => (
            <div key={r.key} className="repo-row">
              <TextField
                id={`repo-${r.key}-name`}
                label={`Repo ${i + 1} name`}
                value={r.name}
                onChange={(v) => update(r.key, { name: v })}
                error={errors[`repo-${r.key}`]}
              />
              <TextField
                id={`repo-${r.key}-full`}
                label={`Repo ${i + 1} org/repo`}
                value={r.github_full_name}
                onChange={(v) => update(r.key, { github_full_name: v })}
              />
              <SelectField
                id={`repo-${r.key}-kind`}
                label={`Repo ${i + 1} kind`}
                value={r.kind ?? 'product'}
                options={KINDS}
                onChange={(v) => update(r.key, { kind: v })}
              />
              <div>
                <button
                  type="button"
                  className="tm-btn btn-ghost"
                  onClick={() => setRepos((rs) => rs.filter((x) => x.key !== r.key))}
                >
                  Remove repo {i + 1}
                </button>
              </div>
            </div>
          ))}
          <div>
            <button
              type="button"
              className="tm-btn btn-ghost"
              onClick={() => {
                const key = nextKey.current++;
                setRepos((rs) => [...rs, { key, name: '', github_full_name: '', kind: 'product' }]);
              }}
            >
              Add a product repo
            </button>
          </div>
        </fieldset>
        <SubmitRow label="Create system" pending={m.isPending} />
      </form>
      {m.isSuccess ? (
        <Result>
          <p className="m-0">
            System <span className="mono">{m.data.code}</span> created in{' '}
            <span className="mono">{m.data.project}</span>.
          </p>
        </Result>
      ) : null}
      {m.isError ? <ActionError error={m.error} /> : null}
    </FormCard>
  );
}

/** Projects and systems (SDD-13 §7.2; SDD-12 §5.3). */
export default function AdminProjects() {
  return (
    <AdminPage
      title="Projects and systems"
      sub="Codes only. A system belongs to one project and names its companion repo and product repos."
    >
      <div className="admin-grid">
        <CreateProject />
        <CreateSystem />
      </div>
      <ProjectsList />
      <SystemsList />
    </AdminPage>
  );
}

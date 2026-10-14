/**
 * Response shapes of the insights read API (SDD-09 §5.6), as the routes in
 * services/insights/app/api/v1/read/*.py, app/api/v1/me.py and app/api/v1/improvement.py build them.
 *
 * Request paths and query parameters are generated from the OpenAPI (schema.d.ts). The OpenAPI
 * declares every read response as an open object (`additionalProperties: true`), so the response
 * bodies are typed here, field by field, from the route code. Rates are fractions 0-1; a ratio
 * with denominator 0 is null (SDD-08 §10.4).
 */

export type Iso = string;

/* ------------------------------------------------------------------ envelope (§5.1.2) */
export interface PeriodMeta {
  key: string;
  from: string | null;
  to: string;
  prev_from: string | null;
  prev_to: string | null;
}

export type ScopeMeta =
  | { level: 'org' }
  | { level: 'all' | 'systems'; projects: string[]; systems: string[] }
  | { level: 'skills' };

export interface Meta {
  generated_at: Iso;
  data_as_of?: Iso | null;
  period?: PeriodMeta;
  scope?: ScopeMeta;
}

export interface Page {
  limit: number;
  next_cursor: string | null;
}

export interface Envelope<T> {
  data: T;
  meta: Meta;
}

export interface PagedEnvelope<T> extends Envelope<{ items: T[] }> {
  page: Page;
}

/** RFC 9457 problem+json (§5.1.4). */
export interface Problem {
  type: string;
  title: string;
  status: number;
  code: string;
  detail: string;
  request_id: string;
}

/* ------------------------------------------------------------------ shared vocabularies */
export type SkillStatus = 'draft' | 'pilot' | 'production' | 'deprecated';
export type PodStatus = SkillStatus;
export type RunStatus = 'RUNNING' | 'PAUSED_INPUT' | 'PAUSED_APPROVAL' | 'COMPLETED';
export type StatusLabel =
  'Running' | 'Needs input' | 'Needs approval' | 'Completed' | 'Aborted' | 'Unknown';
export type Outcome =
  'PASS' | 'PASS-WITH-FINDINGS' | 'RETRY' | 'NEEDS-INPUT' | 'ESCALATE' | 'ABORT';
export type Band = 'high' | 'medium' | 'low';
export type PackStatus = 'fresh' | 'stale' | 'missing' | string;
export type ViewName = 'business' | 'engineer';
export type RoleName =
  'viewer' | 'engineer' | 'tech_lead' | 'skill_owner' | 'stage_approver' | 'eng_lead' | 'admin';

/* ------------------------------------------------------------------ E01 /v1/me */
export interface MeRole {
  role: RoleName;
  scope_type: 'org' | 'client' | 'project' | 'system' | 'skill' | 'stage';
  scope: string | null;
}

export interface MeData {
  pseudonym: string;
  display_name: string | null;
  role_label: string;
  roles: MeRole[];
  agent_role: string | null;
  default_view: ViewName;
  can_switch_view: boolean;
  can_reveal_names: boolean;
  scope: { projects: { code: string; systems: { code: string; domain: string | null }[] }[] };
  app_roles: string[];
}

/* ------------------------------------------------------------------ E02 /v1/status */
export interface StatusData {
  last_event_received_at: Iso | null;
  views_refreshed_at: Iso | null;
  catalogue_release: string | null;
  service_version: string;
  behind: boolean;
  /** ENVIRONMENT of the insights service; `test` shows the TEST ENVIRONMENT banner (ADR 0006). */
  environment?: string;
  identity_provider?: 'entra' | 'github';
}

/* ------------------------------------------------------------------ E03 /v1/catalogue/summary */
export interface SummaryRole {
  id: string;
  code: string;
  label: string;
  skills_production: number;
  skills_pilot: number;
}

export interface Phase {
  id: string;
  label: string;
}

export interface Release {
  tag: string;
  plugin_version: string;
  released_at: Iso | null;
}

export interface SummaryData {
  skills_in_production: number;
  roles_covered: number;
  phases_covered: number;
  pods_ready: number;
  roles: SummaryRole[];
  phases: Phase[];
  domains: string[];
  latest_release: Release | null;
}

/* ------------------------------------------------------------------ E04 /v1/catalogue/skills */
export interface SkillCard {
  id: string;
  title: string;
  summary: string;
  agent_role: string;
  agent_role_label: string;
  phase: string;
  domains: string[];
  status: SkillStatus;
  current_version: string;
  outputs: string[];
  first_try_pass: number | null;
  first_try_n: number;
}

/* ------------------------------------------------------------------ E05 /v1/catalogue/skills/{id} */
export interface SkillInput {
  name: string;
  schema?: string;
  required?: boolean;
  [k: string]: unknown;
}

export interface SkillOutput {
  name: string;
  schema?: string;
  [k: string]: unknown;
}

export interface SkillDetail {
  id: string;
  title: string;
  summary: string;
  agent_role: string;
  agent_role_label: string;
  phase: string;
  domains: string[];
  status: SkillStatus;
  owner_pseudonym: string | null;
  release_tag: string | null;
  portal: { why_clients_care?: string[]; client_receives?: string[] };
  current: {
    version: string;
    inputs: SkillInput[];
    outputs: SkillOutput[];
    context_sections: string[];
    size_budget_tokens: number | null;
    allowed_tools: string[];
  };
  quality: {
    period: string;
    runs: number;
    first_try_pass: number | null;
    band_mix: { high: number | null; medium: number | null; low: number | null };
  };
  eval: {
    version: string;
    pass_rate: number | null;
    cases: number | null;
    recorded_at: Iso | null;
  };
  versions: {
    version: string;
    status: SkillStatus;
    eval_pass_rate: number | null;
    changelog: string | null;
    published_at: Iso | null;
  }[];
  pods: { id: string; title: string }[];
  workflows: {
    workflow_id: string;
    version: string;
    position: number;
    step_count: number;
    after_gate: string | null;
  }[];
}

/* ------------------------------------------------------------------ E06 quality */
export interface SkillQuality {
  skill_id: string;
  version: string;
  scope_level: 'org' | 'systems';
  first_attempts: number;
  causes: { code: string; label: string; n: number }[];
}

/* ------------------------------------------------------------------ E07 releases */
export interface ReleaseNote {
  kind: string;
  id?: string;
  version?: string;
  text: string;
}

export interface ReleaseItem {
  tag: string;
  plugin_version: string;
  tsl_version: string | null;
  released_at: Iso | null;
  notes: ReleaseNote[];
}

/* ------------------------------------------------------------------ E08-E13 pods */
export type PodMetrics =
  | { status: 'no_data' }
  | {
      status: 'ok';
      period: string;
      first_try_pass: number | null;
      systems_served: number;
      prs_merged: number;
      completed_runs: number;
    };

export interface PodCard {
  id: string;
  version: string;
  status: PodStatus;
  kind: string;
  title: string;
  summary: string | null;
  agents: string[];
  code: string[];
  people: (string | null)[];
  engagements: number;
  /** viewer-only callers (SDD-10 §6.1) */
  best_for?: string | null;
  metrics?: PodMetrics;
  /** everyone else */
  workflows?: string[];
  skill_count?: number;
}

export interface PodAgent {
  key: string;
  code: string;
  role: string;
  display_name: string;
  engineers: number | null;
  job: string | null;
  skills?: string[];
}

export interface FlowStep {
  seq: number;
  kind: 'skill' | 'gate' | string;
  label: string;
  who: string;
  step_id?: string;
}

export interface PodDetail {
  id: string;
  version: string;
  status: PodStatus;
  kind: string;
  title: string;
  summary: string | null;
  agents: PodAgent[];
  people_accountable: { role: string | null; decides: string[] }[];
  flow: FlowStep[];
  client_gets: string[];
  good_fit: string[];
  not_a_fit: string[];
  deprecated_by: string | null;
  internal_only: boolean;
  workflows?: string[];
}

export interface PodFit {
  pod_id: string;
  system: string;
  checks: {
    key: string;
    required: unknown;
    status: 'met' | 'not_met' | 'confirm_locally';
    detail: string;
  }[];
}

export interface PodOnePager {
  pod_id: string;
  status: PodStatus;
  markdown: string;
  metrics: PodMetrics;
  internal_only: boolean;
}

/* ------------------------------------------------------------------ E14 capability map */
export interface CapabilityCell {
  skill_id: string;
  title: string;
  status: SkillStatus;
  evidence_backed: boolean;
}

export interface CapabilityMap {
  audience: 'internal' | 'shared';
  phases: Phase[];
  rows: { role: string; code: string; label: string; cells: Record<string, CapabilityCell[]> }[];
  totals: {
    production_skills: number;
    cells_with_skills: number;
    evidence_backed_cells: number;
    runs: number;
    first_try_pass: number | null;
    systems_served: number;
  };
}

/* ------------------------------------------------------------------ E15 business */
export interface BusinessInsights {
  prs_delivered: { value: number; change: number | null };
  first_try_pass: { value: number | null };
  systems_served: { value: number; domains: number };
  engineers_using: { value: number };
  active_pods: { value: number };
  prs_by_month: { month: string; merged: number }[];
  most_used_pods: { pod_id: string; title: string; engagements: number }[];
}

/* ------------------------------------------------------------------ E16 home */
export type WaitingItem =
  | {
      kind: 'question';
      run_id: string;
      ticket_ref: string | null;
      item: string;
      blocking: boolean | null;
      ask_role: string | null;
      since: Iso | null;
      file_url: string | null;
    }
  | {
      kind: 'approval';
      run_id: string;
      ticket_ref: string | null;
      item: string;
      reason_code: string | null;
      since: Iso | null;
    };

export interface HomeData {
  tiles: {
    active_runs: number;
    waiting_on_me: { total: number; questions: number; approvals: number };
    my_first_try_pass: { value: number | null; n: number };
    my_prs_this_month: number;
  };
  waiting: WaitingItem[];
  systems: {
    system: string;
    pack_status: PackStatus | null;
    pack_signed_at: Iso | null;
    days_since_signed: number | null;
    drift_files: number | null;
  }[];
  agent_role: string | null;
}

/* ------------------------------------------------------------------ E17-E20 engineering */
export interface EngRuns {
  status_counts: {
    running: number;
    paused_input: number;
    paused_approval: number;
    completed: number;
    aborted: number;
  };
  oldest_input_wait_s: number | null;
  aborted_by_code: { code: string; n: number }[];
  step_outcomes: { total: number } & Record<Outcome, number | null>;
}

export interface EngSkillRow {
  skill_id: string;
  version: string;
  scope_level: 'org' | 'systems';
  runs: number;
  first_try_pass: number | null;
  below_target: boolean | null;
  band_mix: { high: number | null; medium: number | null; low: number | null };
  retries_per_step: number | null;
  override_rate: number | null;
  top_cause: { code: string; label: string } | null;
  open_flags: number;
  high_band_precision: number | null;
}

export interface EngUsage {
  active_engineers: number;
  runs_started: number;
  pr_merge_rate: number | null;
  prs_without_run: number;
  changes_requested_share: number | null;
  runs_by_workflow: { workflow_id: string; runs: number }[];
  weekly: { week: string; active_engineers: number; runs_started: number }[];
  cost_by_workflow: { workflow_id: string; avg_tokens: number; avg_cost_usd: number }[];
}

export interface EngHealth {
  packs: {
    system: string;
    status: PackStatus | null;
    days_since_signed: number | null;
    drift_files: number | null;
  }[];
  fresh_systems: number;
  ci: { verified: number; e_ci_01: number; e_ci_02: number; e_ci_03: number };
  telemetry: {
    events_today: number;
    devices_with_queue: number;
    plugin_spread: { latest: string | null; on_latest: number; active: number };
    policy_blocks: number;
  } | null;
}

/* ------------------------------------------------------------------ E21-E22 runs */
export interface Person {
  pseudonym: string | null;
  display_name: string | null;
}

export interface NextAction {
  kind: 'none' | 'answer_questions' | 'approve' | 'pr' | string;
  text: string;
  command: string | null;
}

export interface RunItem {
  run_id: string;
  project: string | null;
  system: string | null;
  ticket_ref: string | null;
  workflow: string | null;
  workflow_version: string | null;
  pod: string | null;
  current_step: { step_id: string; position: number | null; step_count: number | null } | null;
  status: RunStatus | null;
  end_reason: string | null;
  end_code: string | null;
  status_label: StatusLabel;
  lowest_band: Band | null;
  engineer: Person;
  is_mine: boolean;
  updated_at: Iso | null;
  is_partial: boolean;
  next_action: NextAction;
}

export type SignalValue =
  number | string | null | { lines?: number; files?: number; sensitive?: boolean };

export interface CheckRecord {
  decided_by: string | null;
  key_id: string | null;
  verification_sha256: string | null;
  signals: Record<string, SignalValue> | null;
  gate_failures: string[];
  caps: string[];
  reasons: { code: string; label: string }[];
  findings: { blocker: number | null; major: number | null; minor: number | null };
  findings_dropped: string[];
  ci_verified: boolean | null;
}

export interface RunStep {
  seq: number | null;
  step_id: string;
  kind: 'skill' | 'gate' | 'pr' | string;
  skill_id: string | null;
  skill_version: string | null;
  outcome: Outcome | 'approved' | 'rejected' | string | null;
  band: Band | null;
  attempt_count: number;
  attempts: {
    attempt: number;
    started_at: Iso | null;
    decided_at: Iso | null;
    duration_ms: number | null;
    record: CheckRecord | null;
  }[];
}

export interface RunDetail {
  run: RunItem;
  pack: { status: PackStatus | null; signed_at: Iso | null; signed_by: string | null };
  links: { companion_runs_url: string };
  steps: RunStep[];
  questions: {
    question_id: string;
    step_id: string | null;
    blocking: boolean | null;
    ask_role: string | null;
    evidence_ref: string | null;
    created_at: Iso | null;
    answered_at: Iso | null;
    age_s: number | null;
    file_url: string;
  }[];
  approvals: {
    gate: string;
    reason_code: string | null;
    requested_at: Iso | null;
    decision: string | null;
    approver: Person | null;
    recorded_at: Iso | null;
  }[];
  pull_requests: {
    repo: string;
    number: number;
    state: string;
    draft: boolean | null;
    url: string;
    ci_result: string | null;
  }[];
  usage: { tokens_in: number; tokens_out: number; cost_usd: number } | null;
}

/* ------------------------------------------------------------------ E23 improvement (SDD-11 §5.4) */
export interface ImprovementFlag {
  flag_id: string;
  skill_id: string;
  skill_version: string;
  signal: string;
  value: number;
  threshold: number;
  sample: number;
  status: string;
  dismissed_reason: string | null;
  opened_at: Iso | null;
  updated_at: Iso | null;
}

export interface ImprovementReport {
  header: {
    skill_id: string;
    version: string;
    owner_pseudonym: string | null;
    window_end: string;
    window_days: number;
    samples: { steps: number; first_attempts: number };
    eval_pass_rate: number | null;
  };
  signals: {
    signal: string;
    value: number | null;
    threshold: number;
    sample: number;
    enough_data: boolean;
  }[];
  not_computed: string[];
  clusters: {
    signature: string;
    count: number;
    share: number | null;
    workflows: string[];
    positions: number[];
    references: { system: string | null; run_id: string; step: string; attempt: number }[];
  }[];
  version_comparison: {
    current: Record<string, number | null>;
    previous: Record<string, number | null> | null;
  };
  improvements: {
    improvement_id: string;
    from_version: string;
    to_version: string;
    state: string;
    before_pass_rate: number | null;
    after_pass_rate: number | null;
  }[];
  flags: ImprovementFlag[];
  window_end: string;
}

/* ------------------------------------------------------------------ admin lists (SDD-13 §7.2) */
/** Rows of the `GET /v1/admin/...` list routes (services/insights/app/api/v1/admin_lists.py). */
export type ConsentStatus = 'recorded' | 'withdrawn' | 'none';
export interface AdminClientRow {
  code: string;
  consent: {
    status: ConsentStatus;
    ref: string | null;
    scope: string[];
    recorded_at: Iso | null;
    withdrawn_at: Iso | null;
  };
  projects: number;
  created_at: Iso | null;
}
export interface AdminProjectRow {
  code: string;
  client: string;
  systems: number;
}
export interface AdminSystemRow {
  code: string;
  project: string;
  client: string;
  domain: string;
  companion_repo: string;
  lifecycle_state: string;
  product_repos: { name: string; github_full_name: string; kind: 'product' | 'read_only' }[];
  created_at: Iso | null;
}
export interface AdminGrantRow {
  id: string;
  user: string;
  role: string;
  scope_type: string;
  scope: string | null;
  status: 'active' | 'revoked';
  granted_at: Iso | null;
  granted_by: string | null;
  revoked_at: Iso | null;
}
export interface AdminUserRow {
  pseudonym: string;
  app_roles: string[];
  roles: string[];
  active: boolean;
  erased: boolean;
  created_at: Iso | null;
  /** Only with `include=names` and only for RD-1 roles; the admin screens never ask for it. */
  display_name: string | null;
}
export interface AdminKeyRow {
  key_id: string;
  device_label: string | null;
  status: 'active' | 'revoked' | 'expired';
  created_at: Iso | null;
  expires_at: Iso | null;
  revoked_at: Iso | null;
  revoked_reason: string | null;
}

/* ------------------------------------------------------------------ path -> response map */
/**
 * Every GET route the portal calls, keyed by its OpenAPI path. `client.ts` checks at compile time
 * that each key is a GET path in the generated schema, so a renamed route fails the build.
 */
export interface ResponseMap {
  '/v1/me': Envelope<MeData>;
  '/v1/status': Envelope<StatusData>;
  '/v1/catalogue/summary': Envelope<SummaryData>;
  '/v1/catalogue/skills': PagedEnvelope<SkillCard>;
  '/v1/catalogue/skills/{skill_id}': Envelope<SkillDetail>;
  '/v1/catalogue/skills/{skill_id}/quality': Envelope<SkillQuality>;
  '/v1/catalogue/releases': PagedEnvelope<ReleaseItem>;
  '/v1/catalogue/pods': PagedEnvelope<PodCard>;
  '/v1/pods/{pod_id}': Envelope<PodDetail>;
  '/v1/pods/{pod_id}/metrics': Envelope<PodMetrics>;
  '/v1/pods/{pod_id}/runs': PagedEnvelope<RunItem>;
  '/v1/pods/{pod_id}/fit': Envelope<PodFit>;
  '/v1/pods/{pod_id}/one-pager': Envelope<PodOnePager>;
  '/v1/capability-map': Envelope<CapabilityMap>;
  '/v1/insights/business': Envelope<BusinessInsights>;
  '/v1/me/home': Envelope<HomeData>;
  '/v1/insights/engineering/runs': Envelope<EngRuns>;
  '/v1/insights/engineering/skills': PagedEnvelope<EngSkillRow>;
  '/v1/insights/engineering/usage': Envelope<EngUsage>;
  '/v1/insights/engineering/health': Envelope<EngHealth>;
  '/v1/runs': PagedEnvelope<RunItem>;
  '/v1/runs/{run_id}': Envelope<RunDetail>;
  '/v1/improvement/skills/{skill_id}': Envelope<ImprovementReport>;
  '/v1/admin/clients': PagedEnvelope<AdminClientRow>;
  '/v1/admin/projects': PagedEnvelope<AdminProjectRow>;
  '/v1/admin/systems': PagedEnvelope<AdminSystemRow>;
  '/v1/admin/role-grants': PagedEnvelope<AdminGrantRow>;
  '/v1/admin/users': PagedEnvelope<AdminUserRow>;
  '/v1/admin/users/{pseudonym}/keys': PagedEnvelope<AdminKeyRow>;
}

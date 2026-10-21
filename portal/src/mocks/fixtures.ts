/**
 * Illustrative data for tests and `npm run demo` only. Every value here is invented: a generic
 * order-tracking and ticketing domain, no client names, no real people, no real systems.
 * The production build never contains this module (scripts/check-bundle.mjs).
 */
import type {
  BusinessInsights,
  CapabilityMap,
  EngHealth,
  EngRuns,
  EngSkillRow,
  EngUsage,
  HomeData,
  ImprovementReport,
  MeData,
  PodCard,
  PodDetail,
  ReleaseItem,
  RunDetail,
  RunItem,
  SkillCard,
  SkillDetail,
  SkillStatus,
  StatusData,
} from '../api/types';

export const ILLUSTRATIVE = 'Illustrative data';

/* ------------------------------------------------------------------ systems and people */
export interface FixtureSystem {
  code: string;
  project: string;
  domain: string;
  companion: string;
}

export const SYSTEMS: FixtureSystem[] = [
  { code: 'SYS-ORD', project: 'PRJ-07', domain: 'digital', companion: 'cl-demo-sys-ord-companion' },
  { code: 'SYS-TKT', project: 'PRJ-07', domain: 'digital', companion: 'cl-demo-sys-tkt-companion' },
  {
    code: 'SYS-INV',
    project: 'PRJ-09',
    domain: 'embedded',
    companion: 'cl-demo-sys-inv-companion',
  },
];

/** Invented, obviously fictitious names for the opt-in name reveal (RD-1). */
export const NAMES: Record<string, string> = {
  'eng-4f2a': 'Avery Example',
  'eng-91c0': 'Jordan Sample',
  'eng-77de': 'Casey Placeholder',
  'eng-0b3e': 'Riley Fixture',
  'eng-7a1c': 'Morgan Demo',
  'eng-5d3e': 'Quinn Mockup',
};

export type DemoUserId = 'viewer' | 'engineer' | 'lead' | 'admin';

export interface DemoUser {
  id: DemoUserId;
  label: string;
  me: MeData;
  /** systems whose runs the user may see (scope, SDD-09 §5.2) */
  systems: string[];
  /** systems whose engineer names the user may reveal (RD-1) */
  nameSystems: string[];
  engineerFamily: boolean;
  telemetry: boolean;
  techLeadSystems: string[];
}

function scopeOf(codes: string[]): MeData['scope'] {
  const projects = new Map<
    string,
    { code: string; systems: { code: string; domain: string | null }[] }
  >();
  for (const s of SYSTEMS.filter((x) => codes.includes(x.code))) {
    const p = projects.get(s.project) ?? { code: s.project, systems: [] };
    p.systems.push({ code: s.code, domain: s.domain });
    projects.set(s.project, p);
  }
  return { projects: [...projects.values()].sort((a, b) => a.code.localeCompare(b.code)) };
}

export const USERS: Record<DemoUserId, DemoUser> = {
  viewer: {
    id: 'viewer',
    label: 'Business viewer (sales)',
    me: {
      pseudonym: 'usr-2b7d',
      display_name: 'Demo Viewer',
      role_label: 'Viewer',
      roles: [{ role: 'viewer', scope_type: 'org', scope: null }],
      agent_role: null,
      default_view: 'business',
      can_switch_view: false,
      can_reveal_names: false,
      scope: { projects: [] },
      app_roles: ['Business'],
    },
    systems: [],
    nameSystems: [],
    engineerFamily: false,
    telemetry: false,
    techLeadSystems: [],
  },
  engineer: {
    id: 'engineer',
    label: 'Engineer and tech lead',
    me: {
      pseudonym: 'eng-4f2a',
      display_name: 'Avery Example',
      role_label: 'Engineer · Tech lead',
      roles: [
        { role: 'engineer', scope_type: 'system', scope: 'SYS-ORD' },
        { role: 'tech_lead', scope_type: 'system', scope: 'SYS-ORD' },
      ],
      agent_role: 'developer',
      default_view: 'engineer',
      can_switch_view: true,
      can_reveal_names: false,
      scope: scopeOf(['SYS-ORD']),
      app_roles: ['Engineer', 'TechLead'],
    },
    systems: ['SYS-ORD'],
    nameSystems: [],
    engineerFamily: true,
    telemetry: true,
    techLeadSystems: ['SYS-ORD'],
  },
  lead: {
    id: 'lead',
    label: 'Engineering lead',
    me: {
      pseudonym: 'eng-7a1c',
      display_name: 'Morgan Demo',
      role_label: 'Engineering lead',
      roles: [{ role: 'eng_lead', scope_type: 'org', scope: null }],
      agent_role: 'solution-architect',
      default_view: 'engineer',
      can_switch_view: true,
      can_reveal_names: true,
      scope: scopeOf(SYSTEMS.map((s) => s.code)),
      app_roles: ['Engineer', 'TechLead'],
    },
    systems: SYSTEMS.map((s) => s.code),
    nameSystems: SYSTEMS.map((s) => s.code),
    engineerFamily: true,
    telemetry: true,
    techLeadSystems: [],
  },
  admin: {
    id: 'admin',
    label: 'Insights admin',
    me: {
      pseudonym: 'eng-5d3e',
      display_name: 'Quinn Mockup',
      role_label: 'Admin',
      roles: [{ role: 'admin', scope_type: 'org', scope: null }],
      agent_role: null,
      default_view: 'engineer',
      can_switch_view: true,
      can_reveal_names: true,
      scope: scopeOf(SYSTEMS.map((s) => s.code)),
      app_roles: ['Admin'],
    },
    systems: SYSTEMS.map((s) => s.code),
    nameSystems: SYSTEMS.map((s) => s.code),
    engineerFamily: true,
    telemetry: true,
    techLeadSystems: [],
  },
};

/* ------------------------------------------------------------------ catalogue */
type S = [
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  number | null,
  SkillStatus,
  string[],
];
// id, title, agent_role, phase, summary, output schema, version, first-try, status, domains
const SKILL_ROWS: S[] = [
  [
    'requirement-review',
    'Requirement review',
    'business-analyst',
    'requirements',
    'Finds gaps, conflicts and missing conditions in a ticket before design starts.',
    'intent.v1',
    '1.2.0',
    0.9,
    'production',
    ['digital', 'embedded'],
  ],
  [
    'story-split',
    'Story split',
    'business-analyst',
    'requirements',
    'Turns reviewed requirements into small, testable user stories.',
    'stories.v1',
    '1.0.0',
    0.86,
    'production',
    ['digital'],
  ],
  [
    'impact-analysis',
    'Impact analysis',
    'solution-architect',
    'design',
    'Shows which modules, APIs and data a change touches, with evidence.',
    'impact.v1',
    '1.1.0',
    0.84,
    'production',
    ['digital', 'embedded'],
  ],
  [
    'design',
    'Solution design',
    'solution-architect',
    'design',
    'Designs the change to fit the existing architecture and rules.',
    'design.v1',
    '1.4.0',
    0.79,
    'production',
    ['digital'],
  ],
  [
    'implement',
    'Implement',
    'developer',
    'build',
    'Writes the code change from an approved design, within change limits.',
    'change.v1',
    '1.0.0',
    0.91,
    'production',
    ['digital', 'embedded', 'iot'],
  ],
  [
    'unit-test',
    'Unit tests',
    'developer',
    'build',
    'Adds and runs unit tests; coverage must not drop.',
    'ut-result.v1',
    '1.0.0',
    0.88,
    'production',
    ['digital'],
  ],
  [
    'defect-triage',
    'Defect triage',
    'developer',
    'operate',
    'Ranks likely root causes of a defect with cited evidence.',
    'triage.v1',
    '1.1.0',
    0.84,
    'production',
    ['digital'],
  ],
  [
    'test-plan',
    'Test plan',
    'qa-engineer',
    'test',
    'Makes sure every acceptance criterion has at least one test.',
    'test-plan.v1',
    '1.0.0',
    0.87,
    'production',
    ['digital'],
  ],
  [
    'test-automation',
    'Test automation',
    'qa-engineer',
    'test',
    'Writes and runs automated tests linked to acceptance criteria.',
    'test-result.v1',
    '0.9.0',
    0.76,
    'pilot',
    [],
  ],
  [
    'pipeline-review',
    'Pipeline review',
    'devops',
    'operate',
    'Reviews CI/CD pipelines for gaps and risky steps.',
    'pipeline-review.v1',
    '0.9.0',
    0.81,
    'pilot',
    [],
  ],
  [
    'deployment-failure-analysis',
    'Deployment failure analysis',
    'devops',
    'operate',
    'Explains a failed deployment from its logs, with cited lines.',
    'deploy-failure.v1',
    '0.8.0',
    0.74,
    'pilot',
    [],
  ],
  [
    'threat-model',
    'Threat model',
    'security',
    'design',
    'Builds a STRIDE threat model from the approved design.',
    'threat-model.v1',
    '1.0.0',
    0.83,
    'production',
    ['digital'],
  ],
  [
    'secure-code-review',
    'Secure code review',
    'security',
    'build',
    'Reviews a code change for security issues with scan results attached.',
    'secure-review.v1',
    '1.0.0',
    0.85,
    'production',
    ['digital'],
  ],
  [
    'ux-flow-review',
    'UX flow review',
    'ux-designer',
    'design',
    'Finds dead ends and missing states in a design flow (read-only).',
    'ux-flow.v1',
    '0.9.0',
    0.8,
    'pilot',
    [],
  ],
  [
    'accessibility-review',
    'Accessibility review',
    'ux-designer',
    'design',
    'Maps design issues to WCAG 2.2 AA criteria.',
    'a11y.v1',
    '0.9.0',
    0.82,
    'pilot',
    [],
  ],
  [
    'estimate-review',
    'Estimate review',
    'delivery-manager',
    'requirements',
    'Sizes work items with evidence; unsized items are flagged, not guessed.',
    'estimate.v1',
    '1.0.0',
    0.8,
    'production',
    [],
  ],
  [
    'status-report',
    'Status report',
    'delivery-manager',
    'operate',
    'Summarises run status, waiting questions and escalations for a project.',
    'status.v1',
    '1.0.0',
    0.95,
    'production',
    [],
  ],
  [
    'release-notes',
    'Release notes',
    'delivery-manager',
    'operate',
    'Drafts release notes from merged pull requests and their check records.',
    'release-notes.v1',
    '0.1.0',
    null,
    'draft',
    [],
  ],
];

export const ROLES: [string, string, string][] = [
  ['business-analyst', 'BA', 'Business Analyst'],
  ['solution-architect', 'SA', 'Solution Architect'],
  ['developer', 'DV', 'Developer'],
  ['qa-engineer', 'QA', 'QA Engineer'],
  ['security', 'SE', 'Security'],
  ['devops', 'DO', 'DevOps'],
  ['ux-designer', 'UX', 'UX Designer'],
  ['delivery-manager', 'DM', 'Delivery Manager'],
];
export const PHASES = [
  { id: 'requirements', label: 'Requirements' },
  { id: 'design', label: 'Design' },
  { id: 'build', label: 'Build' },
  { id: 'test', label: 'Test' },
  { id: 'operate', label: 'Operate' },
];
const ROLE_LABEL = Object.fromEntries(ROLES.map(([id, , l]) => [id, l]));

export const SKILLS: SkillCard[] = SKILL_ROWS.map(
  ([id, title, role, phase, summary, out, ver, ftp, status, domains]) => ({
    id,
    title,
    summary,
    agent_role: role,
    agent_role_label: ROLE_LABEL[role] ?? role,
    phase,
    domains,
    status,
    current_version: ver,
    outputs: [out],
    first_try_pass: ftp,
    first_try_n: ftp === null ? 0 : 40 + id.length,
  }),
);

const WORKFLOW_POSITIONS: Record<string, SkillDetail['workflows']> = {
  'threat-model': [
    {
      workflow_id: 'brownfield-change',
      version: '1.3.0',
      position: 6,
      step_count: 11,
      after_gate: 'G-design',
    },
    {
      workflow_id: 'greenfield-feature',
      version: '1.1.0',
      position: 5,
      step_count: 10,
      after_gate: 'G-design',
    },
  ],
  design: [
    {
      workflow_id: 'brownfield-change',
      version: '1.3.0',
      position: 4,
      step_count: 11,
      after_gate: null,
    },
  ],
  implement: [
    {
      workflow_id: 'brownfield-change',
      version: '1.3.0',
      position: 7,
      step_count: 11,
      after_gate: 'G-design',
    },
    { workflow_id: 'defect-fix', version: '1.0.0', position: 3, step_count: 6, after_gate: null },
  ],
};

const SKILL_PODS: Record<string, { id: string; title: string }[]> = {
  'threat-model': [
    { id: 'brownfield-change-pod', title: 'Brownfield Change Pod' },
    { id: 'quality-security-pod', title: 'Quality and Security Pod' },
  ],
  design: [{ id: 'brownfield-change-pod', title: 'Brownfield Change Pod' }],
  implement: [
    { id: 'brownfield-change-pod', title: 'Brownfield Change Pod' },
    { id: 'greenfield-feature-pod', title: 'Greenfield Feature Pod' },
  ],
};

export function skillDetail(card: SkillCard): SkillDetail {
  const tm = card.id === 'threat-model';
  return {
    id: card.id,
    title: card.title,
    summary: tm
      ? 'Builds a STRIDE threat model from the approved design: every component gets its threats, likely impact and a mitigation, each tied to evidence in the design or the context pack.'
      : card.summary,
    agent_role: card.agent_role,
    agent_role_label: card.agent_role_label,
    phase: card.phase,
    domains: card.domains,
    status: card.status,
    owner_pseudonym: 'skill-owner-9c',
    release_tag: 'v1.6.0',
    portal: tm
      ? {
          why_clients_care: [
            'Security risks are found at design time, when they are cheapest to fix.',
            'Every threat links to evidence, so reviewers can trust it.',
            "The output is ready for the client's security review board.",
          ],
          client_receives: [
            'Threat table: component, STRIDE category, impact, mitigation.',
            'Open questions for the client where facts are missing.',
            'A signed check record showing it passed quality checks.',
          ],
        }
      : {
          why_clients_care: [
            'Work is checked against the real system before a person signs it off.',
          ],
          client_receives: [
            `A ${card.outputs[0] ?? 'checked'} artifact with a signed check record.`,
          ],
        },
    current: {
      version: card.current_version,
      inputs: tm
        ? [{ name: 'design', schema: 'design.v1', required: true }]
        : [{ name: 'ticket', schema: 'intent.v1', required: true }],
      outputs: [{ name: card.id, schema: card.outputs[0] ?? `${card.id}.v1` }],
      context_sections: ['system-baseline#architecture', 'generated/api-inventory.json'],
      size_budget_tokens: 60000,
      allowed_tools: ['Read', 'Grep', 'Glob', 'Write'],
    },
    quality: {
      period: '90d',
      runs: card.first_try_pass === null ? 0 : 64,
      first_try_pass: card.first_try_pass,
      band_mix:
        card.first_try_pass === null
          ? { high: null, medium: null, low: null }
          : { high: 0.71, medium: 0.22, low: 0.07 },
    },
    eval: {
      version: card.current_version,
      pass_rate: card.status === 'draft' ? null : 0.94,
      cases: card.status === 'draft' ? null : 18,
      recorded_at: '2026-09-30T10:00:00Z',
    },
    versions: [
      {
        version: card.current_version,
        status: card.status,
        eval_pass_rate: card.status === 'draft' ? null : 0.94,
        changelog: card.status === 'draft' ? 'First draft' : 'First production release',
        published_at: '2026-09-30T10:00:00Z',
      },
      ...(card.status === 'production'
        ? [
            {
              version: '0.9.0',
              status: 'deprecated' as const,
              eval_pass_rate: 0.88,
              changelog: 'Pilot on two sample systems',
              published_at: '2026-08-01T10:00:00Z',
            },
          ]
        : []),
    ],
    pods: SKILL_PODS[card.id] ?? [],
    workflows: WORKFLOW_POSITIONS[card.id] ?? [],
  };
}

export const RELEASES: ReleaseItem[] = [
  {
    tag: 'v1.6.0',
    plugin_version: '1.6.0',
    tsl_version: '1.6.0',
    released_at: '2026-10-01T08:00:00Z',
    notes: [
      {
        kind: 'skill',
        id: 'design',
        version: '1.4.0',
        text: 'Checks data-retention rules from the context pack.',
      },
      {
        kind: 'skill',
        id: 'threat-model',
        version: '1.0.0',
        text: 'New: STRIDE threat model from the approved design.',
      },
      { kind: 'plugin', text: 'Faster checks; events wait offline and send later.' },
    ],
  },
];

/* ------------------------------------------------------------------ pods */
interface PodRow {
  id: string;
  title: string;
  kind: string;
  status: SkillStatus;
  summary: string;
  agents: {
    key: string;
    code: string;
    role: string;
    name: string;
    job: string;
    skills: string[];
  }[];
  workflows: string[];
  people: { role: string; decides: string[] }[];
  bestFor: string;
  engagements: number;
}

export const POD_ROWS: PodRow[] = [
  {
    id: 'brownfield-change-pod',
    title: 'Brownfield Change Pod',
    kind: 'brownfield',
    status: 'production',
    summary:
      "Change requests on an existing client system, from ticket to a reviewed pull request. Three AI agents do the work; the client's tech lead and product owner make the decisions.",
    agents: [
      {
        key: 'sa',
        code: 'SA',
        role: 'solution-architect',
        name: 'Solution Architect agent',
        job: 'Analyses the impact on the existing system and designs the change to fit its architecture and rules.',
        skills: ['impact-analysis', 'design', 'threat-model'],
      },
      {
        key: 'fs',
        code: 'DV',
        role: 'developer',
        name: 'Full-stack agent',
        job: 'Implements the approved design and its unit tests, inside the change limits set by the tech lead.',
        skills: ['implement', 'unit-test', 'secure-code-review'],
      },
      {
        key: 'qa',
        code: 'QA',
        role: 'qa-engineer',
        name: 'QA agent',
        job: 'Plans tests so every acceptance criterion is covered, and checks results.',
        skills: ['requirement-review', 'story-split', 'test-plan'],
      },
    ],
    workflows: ['brownfield-change', 'defect-fix'],
    people: [
      { role: 'Tech lead', decides: ['signs the context pack', 'approves the design'] },
      { role: 'Product owner', decides: ['answers business questions'] },
      { role: 'Reviewer', decides: ['reviews and merges the PR'] },
    ],
    bestFor: 'Ongoing maintenance and change work',
    engagements: 5,
  },
  {
    id: 'greenfield-feature-pod',
    title: 'Greenfield Feature Pod',
    kind: 'greenfield',
    status: 'production',
    summary: "New features or products designed from the client's goals and constraints.",
    agents: [
      {
        key: 'ba',
        code: 'BA',
        role: 'business-analyst',
        name: 'Business Analyst agent',
        job: 'Turns goals into reviewed requirements and stories.',
        skills: ['requirement-review', 'story-split'],
      },
      {
        key: 'sa',
        code: 'SA',
        role: 'solution-architect',
        name: 'Solution Architect agent',
        job: 'Designs the new feature.',
        skills: ['design', 'threat-model'],
      },
      {
        key: 'dv',
        code: 'DV',
        role: 'developer',
        name: 'Developer agent',
        job: 'Builds and unit-tests the feature.',
        skills: ['implement', 'unit-test'],
      },
      {
        key: 'qa',
        code: 'QA',
        role: 'qa-engineer',
        name: 'QA agent',
        job: 'Plans the tests.',
        skills: ['test-plan'],
      },
    ],
    workflows: ['greenfield-feature'],
    people: [
      { role: 'Tech lead', decides: ['approves the design'] },
      { role: 'Product owner', decides: ['answers business questions'] },
      { role: 'Architect', decides: ['signs off the architecture'] },
    ],
    bestFor: 'New product builds and big features',
    engagements: 2,
  },
  {
    id: 'quality-security-pod',
    title: 'Quality and Security Pod',
    kind: 'quality',
    status: 'pilot',
    summary: 'Test plans, test automation, threat models and secure code review on any codebase.',
    agents: [
      {
        key: 'qa',
        code: 'QA',
        role: 'qa-engineer',
        name: 'QA agent',
        job: 'Plans and automates tests.',
        skills: ['test-plan', 'test-automation'],
      },
      {
        key: 'se',
        code: 'SE',
        role: 'security',
        name: 'Security agent',
        job: 'Threat models and secure code review.',
        skills: ['threat-model', 'secure-code-review'],
      },
      {
        key: 'do',
        code: 'DO',
        role: 'devops',
        name: 'DevOps agent',
        job: 'Reviews pipelines.',
        skills: ['pipeline-review', 'deployment-failure-analysis'],
      },
    ],
    workflows: ['quality-uplift', 'security-review'],
    people: [
      { role: 'QA lead', decides: ['accepts the test plan'] },
      { role: 'Security lead', decides: ['accepts the threat model'] },
    ],
    bestFor: 'Audits and quality uplift',
    engagements: 1,
  },
  {
    id: 'ux-review-pod',
    title: 'UX Review Pod',
    kind: 'ux',
    status: 'pilot',
    summary: 'Flow and accessibility reviews of designs before build, read-only.',
    agents: [
      {
        key: 'ux',
        code: 'UX',
        role: 'ux-designer',
        name: 'UX Designer agent',
        job: 'Reviews flows and accessibility.',
        skills: ['ux-flow-review', 'accessibility-review'],
      },
    ],
    workflows: ['ux-review'],
    people: [
      { role: 'UX lead', decides: ['accepts the review'] },
      { role: 'Product owner', decides: ['prioritises fixes'] },
    ],
    bestFor: 'Design reviews and WCAG checks',
    engagements: 1,
  },
];

export const POD_METRICS: Record<
  string,
  {
    first_try_pass: number;
    systems_served: number;
    prs_merged: number;
    completed_runs: number;
  } | null
> = {
  'brownfield-change-pod': {
    first_try_pass: 0.84,
    systems_served: 3,
    prs_merged: 41,
    completed_runs: 44,
  },
  'greenfield-feature-pod': {
    first_try_pass: 0.79,
    systems_served: 1,
    prs_merged: 9,
    completed_runs: 10,
  },
  'quality-security-pod': null,
  'ux-review-pod': null,
};

export function podCard(p: PodRow, viewerOnly: boolean): PodCard {
  const card: PodCard = {
    id: p.id,
    version: '1.0.0',
    status: p.status,
    kind: p.kind,
    title: p.title,
    summary: p.summary,
    agents: p.agents.map((a) => a.name.replace(/ agent$/, '')),
    code: p.agents.map((a) => a.code),
    people: p.people.map((x) => x.role),
    engagements: p.engagements,
  };
  if (viewerOnly) {
    const m = POD_METRICS[p.id];
    card.best_for = p.bestFor;
    card.metrics = m ? { status: 'ok', period: 'all', ...m } : { status: 'no_data' };
  } else {
    card.workflows = p.workflows;
    card.skill_count = new Set(p.agents.flatMap((a) => a.skills)).size;
  }
  return card;
}

const BROWNFIELD_FLOW: [number, string, string, string, string][] = [
  [1, 'skill', 'requirement-review', 'Requirement review', 'QA agent'],
  [2, 'skill', 'story-split', 'Story split', 'QA agent'],
  [3, 'skill', 'impact-analysis', 'Impact analysis', 'Solution Architect agent'],
  [4, 'skill', 'design', 'Solution design', 'Solution Architect agent'],
  [5, 'gate', 'G-design', 'Approval G-design', 'Tech lead'],
  [6, 'skill', 'threat-model', 'Threat model', 'Solution Architect agent'],
  [7, 'skill', 'implement', 'Implement', 'Full-stack agent'],
  [8, 'skill', 'unit-test', 'Unit tests', 'Full-stack agent'],
  [9, 'skill', 'secure-code-review', 'Secure code review', 'Full-stack agent'],
  [10, 'skill', 'test-plan', 'Test plan', 'QA agent'],
  [11, 'pr', 'pr', 'Pull request', 'Engineer'],
];

export function podDetail(p: PodRow, viewerOnly: boolean): PodDetail {
  const flow = (
    p.id === 'brownfield-change-pod' ? BROWNFIELD_FLOW : BROWNFIELD_FLOW.slice(0, 5)
  ).map(([seq, kind, stepId, label, who]) => ({
    seq,
    kind,
    label,
    who,
    ...(viewerOnly ? {} : { step_id: stepId }),
  }));
  const d: PodDetail = {
    id: p.id,
    version: '1.0.0',
    status: p.status,
    kind: p.kind,
    title: p.title,
    summary: p.summary,
    agents: p.agents.map((a) => ({
      key: a.key,
      code: a.code,
      role: a.role,
      display_name: a.name,
      engineers: 1,
      job: a.job,
      ...(viewerOnly ? {} : { skills: a.skills }),
    })),
    people_accountable: p.people,
    flow,
    client_gets: [
      'Reviewed pull requests with tests and an audit trail',
      'Design and threat model for every change',
      'Clear questions instead of guesses',
    ],
    good_fit: [
      'The client has an existing codebase on GitHub',
      'There is a steady stream of change tickets',
      'A client tech lead can approve designs',
    ],
    not_a_fit: ['The code cannot leave the client network'],
    deprecated_by: null,
    internal_only: p.status !== 'production',
  };
  if (!viewerOnly) d.workflows = p.workflows;
  return d;
}

export function onePagerMarkdown(p: PodRow): string {
  return [
    `# ${p.title}`,
    '',
    p.summary,
    '',
    '## Who is in the pod',
    ...p.agents.map((a) => `- **${a.name}**: ${a.job}`),
    '',
    '## People accountable',
    ...p.people.map((x) => `- ${x.role}: ${x.decides.join(', ')}`),
    '',
    `Best for: *${p.bestFor}*.`,
  ].join('\n');
}

/* ------------------------------------------------------------------ business insights */
export function businessFor(period: string, empty: boolean): BusinessInsights {
  if (empty) {
    return {
      prs_delivered: { value: 0, change: period === 'all' ? null : 0 },
      first_try_pass: { value: null },
      systems_served: { value: 0, domains: 0 },
      engineers_using: { value: 0 },
      active_pods: { value: 0 },
      prs_by_month: [],
      most_used_pods: [],
    };
  }
  const months6: [string, number][] = [
    ['2026-05', 9],
    ['2026-06', 14],
    ['2026-07', 18],
    ['2026-08', 27],
    ['2026-09', 33],
    ['2026-10', 41],
  ];
  const months12: [string, number][] = [
    ['2025-11', 0],
    ['2025-12', 0],
    ['2026-01', 2],
    ['2026-02', 3],
    ['2026-03', 5],
    ['2026-04', 6],
    ...months6,
  ];
  const series =
    period === '90d' ? months6 : period === '12m' ? months12 : months12.filter(([, v]) => v > 0);
  return {
    prs_delivered: {
      value: period === '90d' ? 126 : period === '12m' ? 158 : 158,
      change: period === 'all' ? null : 38,
    },
    first_try_pass: { value: 0.82 },
    systems_served: { value: 7, domains: 4 },
    engineers_using: { value: 48 },
    active_pods: { value: 9 },
    prs_by_month: series.map(([month, merged]) => ({ month, merged })),
    most_used_pods: POD_ROWS.map((p) => ({
      pod_id: p.id,
      title: p.title,
      engagements: p.engagements,
    })),
  };
}

export function capabilityMap(audience: 'internal' | 'shared'): CapabilityMap {
  const rows = ROLES.map(([role, code, label]) => {
    const cells: CapabilityMap['rows'][number]['cells'] = {};
    for (const ph of PHASES) {
      cells[ph.id] = SKILLS.filter(
        (s) =>
          s.agent_role === role &&
          s.phase === ph.id &&
          (s.status === 'production' || (audience === 'internal' && s.status === 'pilot')),
      ).map((s) => ({
        skill_id: s.id,
        title: s.title,
        status: s.status,
        evidence_backed: s.status === 'production' && (s.first_try_n ?? 0) >= 5,
      }));
    }
    return { role, code, label, cells };
  }).filter(
    (r) =>
      audience === 'internal' ||
      Object.values(r.cells).some((c) => c.some((x) => x.status === 'production')),
  );
  const filled = rows.flatMap((r) => Object.values(r.cells)).filter((c) => c.length > 0);
  return {
    audience,
    phases: PHASES,
    rows,
    totals: {
      production_skills: SKILLS.filter((s) => s.status === 'production').length,
      cells_with_skills: filled.length,
      evidence_backed_cells: filled.filter((c) => c.some((x) => x.evidence_backed)).length,
      runs: 412,
      first_try_pass: 0.82,
      systems_served: 7,
    },
  };
}

/* ------------------------------------------------------------------ runs */
const NOW = Date.now();
const ago = (min: number) => new Date(NOW - min * 60_000).toISOString();

interface RunRow {
  id: string;
  system: string;
  ticket: string;
  workflow: string;
  step: string;
  position: number;
  count: number;
  status: RunItem['status'];
  endReason: string | null;
  endCode: string | null;
  band: RunItem['lowest_band'];
  engineer: string;
  updatedMin: number;
  pod: string | null;
  pr: { number: number; state: string } | null;
}

export const RUN_ROWS: RunRow[] = [
  {
    id: 'run_01J9ZK2M4Q8X7T3B5N6R0VWYCD',
    system: 'SYS-ORD',
    ticket: 'ORD-142',
    workflow: 'brownfield-change',
    step: 'design',
    position: 4,
    count: 11,
    status: 'PAUSED_INPUT',
    endReason: null,
    endCode: null,
    band: null,
    engineer: 'eng-4f2a',
    updatedMin: 2880,
    pod: 'brownfield-change-pod',
    pr: null,
  },
  {
    id: 'run_01J9ZM7A2B3C4D5E6F7G8H9JM7',
    system: 'SYS-ORD',
    ticket: 'ORD-150',
    workflow: 'defect-fix',
    step: 'unit-test',
    position: 4,
    count: 6,
    status: 'RUNNING',
    endReason: null,
    endCode: null,
    band: 'high',
    engineer: 'eng-4f2a',
    updatedMin: 5,
    pod: 'brownfield-change-pod',
    pr: null,
  },
  {
    id: 'run_01J9ZP3K5M6N7P8Q9R0S1T2VP3',
    system: 'SYS-ORD',
    ticket: 'ORD-149',
    workflow: 'brownfield-change',
    step: 'implement',
    position: 7,
    count: 11,
    status: 'RUNNING',
    endReason: null,
    endCode: null,
    band: 'medium',
    engineer: 'eng-91c0',
    updatedMin: 12,
    pod: 'brownfield-change-pod',
    pr: null,
  },
  {
    id: 'run_01J8XA4B5C6D7E8F9G0H1J2KA4',
    system: 'SYS-TKT',
    ticket: 'TKT-91',
    workflow: 'greenfield-feature',
    step: 'implement',
    position: 6,
    count: 10,
    status: 'PAUSED_APPROVAL',
    endReason: null,
    endCode: null,
    band: 'low',
    engineer: 'eng-77de',
    updatedMin: 180,
    pod: 'greenfield-feature-pod',
    pr: null,
  },
  {
    id: 'run_01J8XQ1R2S3T4V5W6X7Y8Z9AQ1',
    system: 'SYS-ORD',
    ticket: 'ORD-131',
    workflow: 'brownfield-change',
    step: 'pr',
    position: 11,
    count: 11,
    status: 'COMPLETED',
    endReason: 'pr_opened',
    endCode: null,
    band: 'medium',
    engineer: 'eng-4f2a',
    updatedMin: 1440,
    pod: 'brownfield-change-pod',
    pr: { number: 482, state: 'open' },
  },
  {
    id: 'run_01J8XX5Y6Z7A8B9C0D1E2F3GX5',
    system: 'SYS-INV',
    ticket: 'INV-12',
    workflow: 'defect-fix',
    step: 'implement',
    position: 3,
    count: 6,
    status: 'COMPLETED',
    endReason: 'aborted',
    endCode: 'E-SEC-01',
    band: null,
    engineer: 'eng-0b3e',
    updatedMin: 2900,
    pod: null,
    pr: null,
  },
  {
    id: 'run_01J8XZ9H0J1K2M3N4P5Q6R7SZ9',
    system: 'SYS-TKT',
    ticket: 'TKT-88',
    workflow: 'brownfield-change',
    step: 'pr',
    position: 11,
    count: 11,
    status: 'COMPLETED',
    endReason: 'pr_opened',
    endCode: null,
    band: 'high',
    engineer: 'eng-77de',
    updatedMin: 4320,
    pod: 'brownfield-change-pod',
    pr: { number: 77, state: 'merged' },
  },
  {
    id: 'run_01J8WA1B2C3D4E5F6G7H8J9KW1',
    system: 'SYS-ORD',
    ticket: 'ORD-127',
    workflow: 'brownfield-change',
    step: 'G-design',
    position: 5,
    count: 11,
    status: 'PAUSED_APPROVAL',
    endReason: null,
    endCode: null,
    band: 'low',
    engineer: 'eng-91c0',
    updatedMin: 600,
    pod: 'brownfield-change-pod',
    pr: null,
  },
];

function label(r: RunRow): RunItem['status_label'] {
  if (r.status === 'RUNNING') return 'Running';
  if (r.status === 'PAUSED_INPUT') return 'Needs input';
  if (r.status === 'PAUSED_APPROVAL') return 'Needs approval';
  if (r.endReason === 'aborted') return 'Aborted';
  return r.endReason === 'cancelled' ? 'Cancelled' : 'Completed';
}

function nextAction(r: RunRow): RunItem['next_action'] {
  if (r.status === 'RUNNING')
    return { kind: 'none', text: 'None, Claude is working', command: null };
  if (r.status === 'PAUSED_INPUT')
    return {
      kind: 'answer_questions',
      text: 'Answer open-questions.md, then resume in Claude Code',
      command: `/truminds:resume ${r.id}`,
    };
  if (r.status === 'PAUSED_APPROVAL')
    return {
      kind: 'approve',
      text: 'Tech lead approves the open gate',
      command: `tsl approve ${r.id} <gate>`,
    };
  if (r.endReason === 'aborted')
    return { kind: 'none', text: `Run aborted: ${r.endCode ?? 'unknown'}`, command: null };
  if (r.pr)
    return {
      kind: 'pr',
      text: `PR #${r.pr.number} ${r.pr.state === 'merged' ? 'merged' : 'in review'}`,
      command: null,
    };
  return { kind: 'none', text: 'Completed', command: null };
}

export function runItem(r: RunRow, me: string, revealNames: boolean): RunItem {
  const sys = SYSTEMS.find((s) => s.code === r.system);
  return {
    run_id: r.id,
    project: sys?.project ?? null,
    system: r.system,
    ticket_ref: r.ticket,
    workflow: r.workflow,
    workflow_version: '1.3.0',
    pod: r.pod,
    current_step: { step_id: r.step, position: r.position, step_count: r.count },
    status: r.status,
    end_reason: r.endReason,
    end_code: r.endCode,
    status_label: label(r),
    lowest_band: r.band,
    engineer: {
      pseudonym: r.engineer,
      display_name: revealNames ? (NAMES[r.engineer] ?? null) : null,
    },
    is_mine: r.engineer === me,
    updated_at: ago(r.updatedMin),
    is_partial: false,
    next_action: nextAction(r),
  };
}

export function runDetail(r: RunRow, me: string, revealNames: boolean): RunDetail {
  const item = runItem(r, me, revealNames);
  const sys = SYSTEMS.find((s) => s.code === r.system);
  const companion = `https://github.com/demo-companion-org/${sys?.companion ?? 'companion'}`;
  const steps = BROWNFIELD_FLOW.map(([seq, kind, stepId]) => {
    const done = seq < r.position || (r.status === 'COMPLETED' && r.endReason !== 'aborted');
    const current = seq === r.position;
    const record = (outcome: string, s1: number) => ({
      decided_by: 'tsl@1.6.0',
      key_id: 'key_01J9ABCDEFGHJKMNPQRSTVWXYZ',
      verification_sha256: '3f9a0c1d2e3f4a5b6c7d8e9f00112233445566778899aabbccddeeff00112233',
      signals: {
        S1: s1,
        S2: 1.0,
        S3: 4.2,
        S4: outcome === 'NEEDS-INPUT' ? 1 : 0,
        S5: 'fresh',
        S6: { lines: 0, files: 0, sensitive: false },
      },
      gate_failures: [],
      caps: [],
      reasons: outcome === 'NEEDS-INPUT' ? [{ code: 'S4', label: 'Open blockers' }] : [],
      findings: {
        blocker: outcome === 'NEEDS-INPUT' ? 1 : 0,
        major: 0,
        minor: outcome === 'PASS-WITH-FINDINGS' ? 2 : 0,
      },
      findings_dropped: outcome === 'NEEDS-INPUT' ? ['F-3'] : [],
      ci_verified: null,
    });
    if (kind === 'gate') {
      return {
        seq,
        step_id: stepId,
        kind,
        skill_id: null,
        skill_version: null,
        outcome: done ? 'approved' : null,
        band: null,
        attempt_count: 0,
        attempts: [],
      };
    }
    if (!done && !current) {
      return {
        seq,
        step_id: stepId,
        kind,
        skill_id: kind === 'skill' ? stepId : null,
        skill_version: null,
        outcome: null,
        band: null,
        attempt_count: 0,
        attempts: [],
      };
    }
    const outcome =
      current && r.status === 'PAUSED_INPUT'
        ? 'NEEDS-INPUT'
        : seq === 2
          ? 'PASS-WITH-FINDINGS'
          : 'PASS';
    const retried = seq === 3;
    const attempts = (retried ? [1, 2] : [1]).map((a) => ({
      attempt: a,
      started_at: ago(r.updatedMin + 300 - seq * 10 - a),
      decided_at: ago(r.updatedMin + 290 - seq * 10 - a),
      duration_ms: 41000,
      record: record(retried && a === 1 ? 'RETRY' : outcome, retried && a === 1 ? 0.71 : 0.91),
    }));
    return {
      seq,
      step_id: stepId,
      kind,
      skill_id: kind === 'skill' ? stepId : null,
      skill_version: '1.0.0',
      outcome: current && r.status === 'RUNNING' ? null : outcome,
      band: outcome === 'NEEDS-INPUT' ? null : seq === 2 ? ('medium' as const) : ('high' as const),
      attempt_count: attempts.length,
      attempts,
    };
  });
  return {
    run: item,
    pack: {
      status: r.system === 'SYS-INV' ? 'stale' : 'fresh',
      signed_at: ago(7200),
      signed_by: 'eng-7a1c',
    },
    links: { companion_runs_url: `${companion}/tree/main/runs/${r.id}` },
    steps,
    questions:
      r.status === 'PAUSED_INPUT'
        ? [
            {
              question_id: 'Q-01',
              step_id: r.step,
              blocking: true,
              ask_role: 'product_owner',
              evidence_ref: 'context/system-baseline.md#data-retention',
              created_at: ago(r.updatedMin),
              answered_at: null,
              age_s: r.updatedMin * 60,
              file_url: `${companion}/blob/main/runs/${r.id}/open-questions.md`,
            },
          ]
        : [],
    approvals:
      r.position >= 5
        ? [
            {
              gate: 'G-design',
              reason_code: r.status === 'PAUSED_APPROVAL' ? 'S6' : null,
              requested_at: ago(r.updatedMin + 30),
              decision: r.status === 'PAUSED_APPROVAL' && r.position === 5 ? null : 'approved',
              approver:
                r.status === 'PAUSED_APPROVAL' && r.position === 5
                  ? null
                  : {
                      pseudonym: 'eng-7a1c',
                      display_name: revealNames ? (NAMES['eng-7a1c'] ?? null) : null,
                    },
              recorded_at:
                r.status === 'PAUSED_APPROVAL' && r.position === 5 ? null : ago(r.updatedMin + 20),
            },
          ]
        : [],
    pull_requests: r.pr
      ? [
          {
            repo: 'orders-api',
            number: r.pr.number,
            state: r.pr.state,
            draft: false,
            url: `https://github.com/demo-product-org/orders-api/pull/${r.pr.number}`,
            ci_result: 'pass',
          },
        ]
      : [],
    usage: { tokens_in: 812000, tokens_out: 96000, cost_usd: 4.21 },
  };
}

/* ------------------------------------------------------------------ home and engineering */
export function homeFor(user: DemoUser): HomeData {
  const mine = RUN_ROWS.filter((r) => r.engineer === user.me.pseudonym);
  const questions = mine.filter((r) => r.status === 'PAUSED_INPUT');
  const approvals = RUN_ROWS.filter(
    (r) =>
      r.status === 'PAUSED_APPROVAL' &&
      user.techLeadSystems.includes(r.system) &&
      r.engineer !== user.me.pseudonym,
  );
  const waiting: HomeData['waiting'] = [
    ...questions.map((r) => ({
      kind: 'question' as const,
      run_id: r.id,
      ticket_ref: r.ticket,
      item: 'Q-01',
      blocking: true,
      ask_role: 'product_owner',
      since: ago(r.updatedMin),
      file_url: `https://github.com/demo-companion-org/${SYSTEMS.find((s) => s.code === r.system)?.companion}/blob/main/runs/${r.id}/open-questions.md`,
    })),
    ...approvals.map((r) => ({
      kind: 'approval' as const,
      run_id: r.id,
      ticket_ref: r.ticket,
      item: 'G-design',
      reason_code: 'S6',
      since: ago(r.updatedMin),
    })),
  ];
  return {
    tiles: {
      active_runs: mine.filter((r) => r.status !== 'COMPLETED').length,
      waiting_on_me: {
        total: waiting.length,
        questions: questions.length,
        approvals: approvals.length,
      },
      my_first_try_pass: { value: 0.78, n: 30 },
      my_prs_this_month: 5,
    },
    waiting,
    systems: user.systems.map((code) => ({
      system: code,
      pack_status: code === 'SYS-INV' ? 'stale' : 'fresh',
      pack_signed_at: ago(code === 'SYS-INV' ? 41 * 1440 : 5 * 1440),
      days_since_signed: code === 'SYS-INV' ? 41 : 5,
      drift_files: code === 'SYS-INV' ? 63 : 0,
    })),
    agent_role: user.me.agent_role,
  };
}

export function engRuns(systems: string[], empty: boolean): EngRuns {
  const rows = RUN_ROWS.filter((r) => systems.includes(r.system));
  if (empty) {
    return {
      status_counts: {
        running: 0,
        paused_input: 0,
        paused_approval: 0,
        completed: 0,
        cancelled: 0,
        aborted: 0,
      },
      oldest_input_wait_s: null,
      aborted_by_code: [],
      step_outcomes: {
        total: 0,
        PASS: null,
        'PASS-WITH-FINDINGS': null,
        RETRY: null,
        'NEEDS-INPUT': null,
        ESCALATE: null,
        ABORT: null,
      },
    };
  }
  const aborted = rows.filter((r) => r.endReason === 'aborted');
  return {
    status_counts: {
      running: rows.filter((r) => r.status === 'RUNNING').length + 10,
      paused_input: rows.filter((r) => r.status === 'PAUSED_INPUT').length + 4,
      paused_approval: rows.filter((r) => r.status === 'PAUSED_APPROVAL').length + 1,
      completed:
        rows.filter(
          (r) =>
            r.status === 'COMPLETED' && r.endReason !== 'aborted' && r.endReason !== 'cancelled',
        ).length + 56,
      cancelled: rows.filter((r) => r.endReason === 'cancelled').length,
      aborted: aborted.length,
    },
    oldest_input_wait_s: 172800,
    aborted_by_code: aborted.map((r) => ({ code: r.endCode ?? 'unknown', n: 1 })),
    step_outcomes: {
      total: 412,
      PASS: 0.58,
      'PASS-WITH-FINDINGS': 0.2,
      RETRY: 0.12,
      'NEEDS-INPUT': 0.06,
      ESCALATE: 0.03,
      ABORT: 0.01,
    },
  };
}

export const ENG_SKILLS: EngSkillRow[] = [
  [
    'requirement-review',
    '1.2.0',
    86,
    0.9,
    [0.7, 0.24, 0.06],
    0.2,
    0.04,
    ['H2', 'Missing Unknown section'],
    0,
  ],
  [
    'design',
    '1.4.0',
    61,
    0.79,
    [0.52, 0.33, 0.15],
    0.5,
    0.09,
    ['REVIEW-MAJOR', 'Reviewer major finding'],
    1,
  ],
  ['implement', '1.0.0', 58, 0.91, [0.74, 0.21, 0.05], 0.3, 0.05, ['H3', 'Test failure'], 0],
  ['unit-test', '1.0.0', 55, 0.88, [0.69, 0.25, 0.06], 0.4, 0.03, ['H7', 'Coverage dropped'], 0],
  [
    'threat-model',
    '1.0.0',
    40,
    0.83,
    [0.71, 0.22, 0.07],
    0.3,
    0.06,
    ['S1', 'Evidence below threshold'],
    0,
  ],
  [
    'test-automation',
    '0.9.0',
    19,
    0.76,
    [0.48, 0.34, 0.18],
    0.7,
    0.12,
    ['H6', 'Stale design input'],
    1,
  ],
].map(([skill_id, version, runs, ftp, b, r, o, c, f]) => {
  const bands = b as number[];
  const cause = c as string[];
  return {
    skill_id: skill_id as string,
    version: version as string,
    scope_level: 'systems' as const,
    runs: runs as number,
    first_try_pass: ftp as number,
    below_target: (ftp as number) < 0.8,
    band_mix: { high: bands[0] ?? null, medium: bands[1] ?? null, low: bands[2] ?? null },
    retries_per_step: r as number,
    override_rate: o as number,
    top_cause: { code: cause[0] ?? '', label: cause[1] ?? '' },
    open_flags: f as number,
    high_band_precision: null,
  };
});

export const ENG_USAGE: EngUsage = {
  active_engineers: 31,
  runs_started: 80,
  pr_merge_rate: 0.91,
  prs_without_run: 4,
  changes_requested_share: 0.18,
  runs_by_workflow: [
    { workflow_id: 'brownfield-change', runs: 44 },
    { workflow_id: 'defect-fix', runs: 20 },
    { workflow_id: 'greenfield-feature', runs: 10 },
    { workflow_id: 'ux-review', runs: 4 },
    { workflow_id: 'estimate', runs: 2 },
  ],
  weekly: [
    { week: '2026-W38', active_engineers: 18, runs_started: 14 },
    { week: '2026-W39', active_engineers: 20, runs_started: 17 },
    { week: '2026-W40', active_engineers: 22, runs_started: 19 },
    { week: '2026-W41', active_engineers: 25, runs_started: 21 },
  ],
  cost_by_workflow: [
    { workflow_id: 'brownfield-change', avg_tokens: 905000, avg_cost_usd: 4.6 },
    { workflow_id: 'defect-fix', avg_tokens: 410000, avg_cost_usd: 2.1 },
  ],
};

export function engHealth(systems: string[], telemetry: boolean): EngHealth {
  const packs = systems.map((code) => ({
    system: code,
    status: code === 'SYS-INV' ? 'stale' : 'fresh',
    days_since_signed: code === 'SYS-INV' ? 41 : code === 'SYS-TKT' ? 12 : 5,
    drift_files: code === 'SYS-INV' ? 63 : 0,
  }));
  return {
    packs,
    fresh_systems: packs.filter((p) => p.status === 'fresh').length,
    ci: { verified: 62, e_ci_01: 4, e_ci_02: 0, e_ci_03: 1 },
    telemetry: telemetry
      ? {
          events_today: 3214,
          devices_with_queue: 2,
          plugin_spread: { latest: '1.6.0', on_latest: 27, active: 31 },
          policy_blocks: 9,
        }
      : null,
  };
}

export function statusData(behind: boolean): StatusData {
  return {
    last_event_received_at: ago(behind ? 190 : 1),
    views_refreshed_at: ago(behind ? 45 : 3),
    catalogue_release: 'v1.6.0',
    service_version: '1.6.0',
    behind,
  };
}

export function improvementReport(skillId: string): ImprovementReport {
  return {
    header: {
      skill_id: skillId,
      version: '1.4.0',
      owner_pseudonym: 'skill-owner-9c',
      window_end: '2026-10-12',
      window_days: 28,
      samples: { steps: 61, first_attempts: 52 },
      eval_pass_rate: 0.94,
    },
    signals: [
      { signal: 'IS-1', value: 0.79, threshold: 0.8, sample: 52, enough_data: true },
      { signal: 'IS-2', value: 0.5, threshold: 0.6, sample: 61, enough_data: true },
      { signal: 'IS-7', value: 0.09, threshold: 0.1, sample: 61, enough_data: true },
    ],
    not_computed: ['IS-3', 'IS-4', 'IS-6', 'IS-9'],
    clusters: [
      {
        signature: 'RETRY|-|S3|major:1|-',
        count: 6,
        share: 0.55,
        workflows: ['brownfield-change'],
        positions: [4],
        references: [
          {
            system: 'SYS-ORD',
            run_id: 'run_01J9ZK2M4Q8X7T3B5N6R0VWYCD',
            step: 'design',
            attempt: 1,
          },
          {
            system: 'SYS-ORD',
            run_id: 'run_01J9ZP3K5M6N7P8Q9R0S1T2VP3',
            step: 'design',
            attempt: 1,
          },
        ],
      },
    ],
    version_comparison: {
      current: { 'IS-1': 0.79, 'IS-2': 0.5, 'IS-7': 0.09 },
      previous: { 'IS-1': 0.74, 'IS-2': 0.62, 'IS-7': 0.11 },
    },
    improvements: [
      {
        improvement_id: 'imp_01JA2CDEFGHJKMNPQRSTVWXYZ0',
        from_version: '1.3.0',
        to_version: '1.4.0',
        state: 'RELEASED',
        before_pass_rate: 0.82,
        after_pass_rate: 0.94,
      },
    ],
    flags: [
      {
        flag_id: 'flg_01JA1ZABCDEFGHJKMNPQRSTVWX',
        skill_id: skillId,
        skill_version: '1.4.0',
        signal: 'IS-1',
        value: 0.79,
        threshold: 0.8,
        sample: 52,
        status: 'OPEN',
        dismissed_reason: null,
        opened_at: '2026-10-06T06:00:00Z',
        updated_at: '2026-10-12T06:00:00Z',
      },
    ],
    window_end: '2026-10-12',
  };
}

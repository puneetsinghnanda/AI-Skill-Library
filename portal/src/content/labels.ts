/** Static labels reviewed like code (SDD-09 §3.2 content/labels.ts). */
import { humanize } from '../lib/format';

/** Harness signals S1-S6 (SDD-03; RunDetail board). */
export const SIGNAL_LABELS: Record<string, string> = {
  S1: 'Evidence coverage',
  S2: 'Soft checks',
  S3: 'Reviewer score',
  S4: 'Open blockers',
  S5: 'Context',
  S6: 'Change risk',
};

export function signalLabel(code: string | null | undefined): string {
  if (!code) return '';
  return SIGNAL_LABELS[code] ? `${code} ${SIGNAL_LABELS[code]}` : code;
}

/** Roles that answer questions or approve gates. */
const ASK_ROLE: Record<string, string> = {
  product_owner: 'Product owner',
  tech_lead: 'Tech lead',
  engineer: 'Engineer',
  reviewer: 'Reviewer',
  security_lead: 'Security lead',
};

export function askRoleLabel(role: string | null | undefined): string {
  if (!role) return 'Someone on the team';
  return ASK_ROLE[role] ?? humanize(role);
}

/** Abort and CI codes shown on the monitoring tiles (registry §2). */
const CODE_WORDS: Record<string, string> = {
  'E-SEC-01': 'secret found',
  'E-POL-01': 'blocked action',
  'E-CI-01': 'missing records',
  'E-CI-02': 'signature problems',
  'E-CI-03': 're-check mismatch',
};

export function codeWords(code: string): string {
  return CODE_WORDS[code] ? `${CODE_WORDS[code]} (${code})` : code;
}

export const POD_KIND: Record<string, string> = {
  brownfield: 'Brownfield',
  greenfield: 'Greenfield',
  quality: 'Quality',
  ux: 'UX',
};

export const ENG_TABS = [
  { id: 'runs', label: 'Runs' },
  { id: 'skills', label: 'Skill performance' },
  { id: 'usage', label: 'Usage' },
  { id: 'health', label: 'Health' },
] as const;

export type EngTab = (typeof ENG_TABS)[number]['id'];

export const ROLE_WORDS: Record<string, string> = {
  viewer: 'viewers',
  engineer: 'engineers',
  tech_lead: 'tech leads',
  skill_owner: 'skill owners',
  stage_approver: 'stage approvers',
  eng_lead: 'engineering leads',
  admin: 'admins',
};

/** "engineering leads and admins" from a role list (RD-1 wording). */
export function roleList(roles: readonly string[]): string {
  const words = roles.map((r) => ROLE_WORDS[r] ?? humanize(r));
  if (words.length <= 1) return words.join('');
  return `${words.slice(0, -1).join(', ')} and ${words[words.length - 1]}`;
}

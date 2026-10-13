/**
 * Open policy decisions (registry §11), as configuration rather than code. The server enforces each
 * of them (services/insights/app/config.py); the portal only shapes its wording and controls to match.
 * Defaults are the registry recommendations.
 */
import type { RoleName } from '../api/types';

const raw = import.meta.env;

function roles(v: string | undefined, fallback: RoleName[]): RoleName[] {
  if (!v || !v.trim()) return fallback;
  return v.split(',').map((x) => x.trim()) as RoleName[];
}

export const policy = {
  /** RD-1: who may reveal engineers' names (opt-in, audited by the server). Default (a). */
  rd1NameRevealRoles: roles(raw.VITE_RD1_NAME_REVEAL_ROLES, ['eng_lead', 'admin']),
  /** RD-2: runs an engineer sees. Default (a) own systems. Scope is resolved by the server only. */
  rd2EngineerRunScope: (raw.VITE_RD2_ENGINEER_RUN_SCOPE === 'project' ? 'project' : 'system') as
    'system' | 'project',
  /** RD-3: question text is never in the cloud (X-06). Default (a): link to open-questions.md. */
  rd3QuestionTextInCloud: raw.VITE_RD3_QUESTION_TEXT_IN_CLOUD === 'true',
  /** RD-5: G2 is measured as M-03 first-try pass rate in Release 1. */
  rd5FirstPassMetric: 'first_try' as const,
  /** RD-6: Doc 3 workflow names are canonical. */
  rd6WorkflowNames: 'doc3' as const,
  /** Amber threshold for first-try pass (Doc 4 §2.0.4). The server also sends `below_target`. */
  firstTryTarget: 0.8,
} as const;

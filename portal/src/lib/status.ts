/**
 * Status words and tones (Doc 4 §2.0.4 status colours, §6.1 tokens). Every status is shown as an
 * icon plus a word, never colour alone (TC-POR-007).
 */
import type { Band, Outcome, PackStatus, SkillStatus, StatusLabel } from '../api/types';

export type Tone =
  'pass' | 'find' | 'retry' | 'input' | 'esc' | 'abort' | 'cancel' | 'navy' | 'teal';

export interface StatusWord {
  tone: Tone;
  word: string;
}

export const OUTCOME: Record<Outcome, StatusWord> = {
  PASS: { tone: 'pass', word: 'Pass' },
  'PASS-WITH-FINDINGS': { tone: 'find', word: 'Pass with findings' },
  RETRY: { tone: 'retry', word: 'Retry' },
  'NEEDS-INPUT': { tone: 'input', word: 'Needs input' },
  ESCALATE: { tone: 'esc', word: 'Escalate' },
  ABORT: { tone: 'abort', word: 'Abort' },
};

export function outcomeStatus(outcome: string | null | undefined, attempts = 1): StatusWord {
  if (!outcome) return { tone: 'retry', word: 'Not started' };
  if (outcome === 'approved') return { tone: 'pass', word: 'Approved' };
  if (outcome === 'rejected') return { tone: 'abort', word: 'Rejected' };
  if (outcome === 'opened') return { tone: 'find', word: 'PR opened' };
  if (outcome === 'merged') return { tone: 'pass', word: 'Merged' };
  const s = OUTCOME[outcome as Outcome];
  if (!s) return { tone: 'retry', word: outcome };
  if (attempts > 1 && (outcome === 'PASS' || outcome === 'PASS-WITH-FINDINGS')) {
    return { tone: 'retry', word: `Retry, then ${s.word.toLowerCase()}` };
  }
  return s;
}

export const RUN_STATUS: Record<StatusLabel, Tone> = {
  Running: 'find',
  'Needs input': 'input',
  'Needs approval': 'esc',
  Completed: 'pass',
  Cancelled: 'cancel',
  Aborted: 'abort',
  Unknown: 'retry',
};

export function runStatus(label: StatusLabel): StatusWord {
  return { tone: RUN_STATUS[label] ?? 'retry', word: label };
}

export function skillStatus(s: SkillStatus): StatusWord {
  switch (s) {
    case 'production':
      return { tone: 'pass', word: 'Production' };
    case 'pilot':
      return { tone: 'input', word: 'Pilot' };
    case 'draft':
      return { tone: 'retry', word: 'Draft' };
    default:
      return { tone: 'retry', word: 'Deprecated' };
  }
}

/** Pods use "Available" for production, as the prototype boards do (Doc 4 §2.0.3). */
export function podStatus(s: SkillStatus): StatusWord {
  return s === 'production' ? { tone: 'pass', word: 'Available' } : skillStatus(s);
}

/** The API sends High, Medium or Low; compare without case so no band falls through to Low. */
export function bandStatus(b: Band | null | undefined): StatusWord | null {
  if (!b) return null;
  const v = b.toLowerCase();
  if (v === 'high') return { tone: 'pass', word: 'High' };
  if (v === 'medium') return { tone: 'find', word: 'Medium' };
  return { tone: 'esc', word: 'Low' };
}

export function packStatus(s: PackStatus | null | undefined): StatusWord {
  if (s === 'fresh') return { tone: 'pass', word: 'Fresh' };
  if (s === 'stale') return { tone: 'input', word: 'Stale' };
  if (!s) return { tone: 'retry', word: 'No pack' };
  return { tone: 'retry', word: s.charAt(0).toUpperCase() + s.slice(1) };
}

export function fitStatus(s: string): StatusWord {
  if (s === 'met') return { tone: 'pass', word: 'Met' };
  if (s === 'not_met') return { tone: 'abort', word: 'Not met' };
  return { tone: 'input', word: 'Confirm locally' };
}

export function prStatus(state: string, draft: boolean | null): StatusWord {
  if (state === 'merged') return { tone: 'pass', word: 'Merged' };
  if (state === 'closed') return { tone: 'retry', word: 'Closed' };
  return draft ? { tone: 'retry', word: 'Draft' } : { tone: 'find', word: 'Open' };
}

export function ciStatus(r: string | null): StatusWord {
  if (r === 'pass') return { tone: 'pass', word: 'CI passed' };
  if (r === 'fail') return { tone: 'abort', word: 'CI failed' };
  return { tone: 'retry', word: 'CI pending' };
}

export function flagStatus(s: string): StatusWord {
  if (s === 'OPEN' || s === 'REOPENED')
    return { tone: 'input', word: s === 'OPEN' ? 'Open' : 'Reopened' };
  if (s === 'IN_PROGRESS' || s === 'PROPOSED')
    return { tone: 'find', word: s === 'IN_PROGRESS' ? 'In progress' : 'Proposed' };
  if (s === 'RELEASED' || s === 'VERIFIED')
    return { tone: 'pass', word: s === 'RELEASED' ? 'Released' : 'Verified' };
  return { tone: 'retry', word: 'Dismissed' };
}

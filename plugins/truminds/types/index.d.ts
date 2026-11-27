// State contract of the truminds Mods module (hooks/register.tsx). The progress panel keeps the
// last answer of `tsl state show --progress --json` (SDD-04) in $.state, so it survives a reload.

export type Band = 'High' | 'Medium' | 'Low'

export type Step = {
  id: string
  kind: string
  status: string
  attempt: number | null
  band: Band | null
}

export type Waiting = {
  kind: 'input' | 'approval' | 'resume'
  gate: string | null
  role: string | null
  // kind 'resume' only: the signed decision (approve | changes | reject | abort)
  decision?: string | null
  command: string
  file: string | null
}

// ask 'ide': asked in an AskUserQuestion dialog that is open now, since its asked_at (UTC).
export type Question = { id: string; blocking: boolean; ask: string | null; text: string; since?: string | null }

export type Progress = {
  run_id: string
  ticket: string
  workflow: string
  status: 'RUNNING' | 'PAUSED_INPUT' | 'PAUSED_APPROVAL' | 'COMPLETED'
  end_reason: string | null
  updated_at: string
  bound: boolean
  current: string | null
  position: { n: number; of: number } | null
  steps: Step[]
  waiting: Waiting | null
  // open_blocking / open_non_blocking count open-questions.md; open_ide the open IDE questions,
  // which come first in items. Older tsl versions send no open_ide.
  questions: { open_blocking: number; open_non_blocking: number; open_ide?: number; items: Question[] }
  // The engineer's wait on IDE questions, in seconds (tsl 0.1.8+).
  wait?: { total_s: number; steps: Record<string, number> }
  // No activity for longer than the open phase allows (D2), else null. Older tsl sends none.
  stuck?: { since: string; minutes: number; phase: string; limit_min: number; command: string; cancel: string } | null
}

// progress: null is "no run in this session". at: local time of the last good answer.
// stale: tsl did not answer the last refresh, so progress is the last good answer.
export type Panel = { progress: Progress | null; at: string | null; stale: boolean }

declare module 'claude-code' {
  interface PluginState {
    truminds: { panel: Shaped<Panel> }
  }
}

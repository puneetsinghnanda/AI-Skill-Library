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
  command: string
  file: string | null
}

export type Question = { id: string; blocking: boolean; ask: string | null; text: string }

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
  questions: { open_blocking: number; open_non_blocking: number; items: Question[] }
}

// progress: null is "no run in this session". at: local time of the last good answer.
// stale: tsl did not answer the last refresh, so progress is the last good answer.
export type Panel = { progress: Progress | null; at: string | null; stale: boolean }

declare module 'claude-code' {
  interface PluginState {
    truminds: { panel: Shaped<Panel> }
  }
}

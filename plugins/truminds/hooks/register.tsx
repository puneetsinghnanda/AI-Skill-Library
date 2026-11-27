import { atom, read, update } from 'claude-code'
import type { Register, RenderElement } from 'claude-code'
import type { Panel, Progress } from '../types'

// Two Mods, both display only (roadmap 12-20 Nov, item 5; SDD-05):
// - /tsl-gate: decide on an approval gate. tsl decides, signs and pushes.
// - The progress panel and /tsl-panel: the run of this session, its steps and bands, what a
//   paused run waits on and its open questions. It reads `tsl state show --progress`, which is
//   local and read only, and never decides, signs or blocks: when tsl is slow, missing or too
//   old, the panel keeps its last answer or shows nothing. Where Mods are off,
//   /truminds:status shows the same run.

// ---------------------------------------------------------------- progress panel

const PANE = 'truminds-run'
const TITLE = 'Truminds run'
const TSL_TIMEOUT_MS = 8000
const POLL_MS = 30000 // only while a run waits for someone else's approval
// The pre-tool hook records an IDE question as its dialog opens: refresh once it has.
const ASK_REFRESH_MS = 1500
const EMPTY: Panel = { progress: null, at: null, stale: false }
// Change the shape tag when Panel changes: it drops what an older version stored.
const panel = atom({ plugin: 'truminds', key: 'panel' } as const, EMPTY, { shape: 'panel-1' })

type Row = { text: string; color?: string | undefined; dim?: boolean; bold?: boolean }

// Set when tsl says this is not a companion repo, or cannot be started at all: the end of each
// turn then stops calling tsl. A tsl command, /tsl-panel, /tsl-gate or a /truminds: command
// tries again.
let idle = false
const NO_REPO = Symbol('no-repo')

// The progress in tsl's answer; null for "no run here"; undefined when tsl gave no usable
// answer (missing, timed out, too old for --progress, an error), so the last answer stays.
function parseProgress(stdout: string): Progress | null | undefined | typeof NO_REPO {
  const line = stdout.trim().split(/\r?\n/).filter(Boolean).pop() ?? ''
  let env: any
  try {
    env = JSON.parse(line)
  } catch {
    return undefined
  }
  if (env?.ok === true && env.data && 'progress' in env.data) return env.data.progress ?? null
  if (env?.code === 'E-REPO-01') return NO_REPO // not a companion repo: nothing to show
  return undefined
}

// A Bash or PowerShell call that ran tsl (the run loop's next, verify, review record, decide,
// pr...). PowerShell is the main shell on Windows hosts.
const SHELLS = ['Bash', 'PowerShell']
function isTslCommand(command: unknown): boolean {
  return typeof command === 'string' && /(^|[\s;&|(])tsl(\.exe)?(\s|$)/.test(command)
}
// An update (roadmap D4): while `uv tool install` replaces tsl, a refresh can find no tsl and the
// panel goes quiet. Once the update command has finished, tsl is back, so try again.
function isUpdateCommand(command: unknown): boolean {
  return (
    typeof command === 'string' &&
    (/(^|[\s;&|(])uv\s+tool\s+install\b.*[\s/\\]tsl(\s|$)/.test(command) ||
      /(^|[\s;&|(])claude\s+plugin\s+(marketplace\s+)?update\b/.test(command))
  )
}

const DONE = ['DONE', 'ACCEPTED', 'APPROVED']
const BAND_COLOR: Record<string, string> = { High: 'success', Medium: 'warning', Low: 'error' }

function stepRow(s: Progress['steps'][number], current: string | null, width: number): Row {
  const name = s.id.padEnd(width) + ' ' // gate ids such as G-threat-review run past 10
  if (DONE.includes(s.status)) {
    return { text: `✓ ${name}${s.band ?? ''}`, color: s.band ? BAND_COLOR[s.band] : undefined }
  }
  if (s.id === current || s.status === 'IN_PROGRESS') {
    const att = s.attempt ? `attempt ${s.attempt}` : 'running'
    return { text: `▶ ${name}${att}`, bold: true }
  }
  if (s.status === 'WAITING_INPUT' || s.status === 'WAITING_APPROVAL') {
    return { text: `⏸ ${name}waiting`, color: 'warning' }
  }
  if (s.status === 'FAILED') return { text: `✗ ${name}failed`, color: 'error' }
  if (s.status === 'STALE') return { text: `↺ ${name}to redo`, dim: true }
  return { text: `· ${s.id}`, dim: true }
}

function waitingRows(p: Progress): Row[] {
  const w = p.waiting
  if (!w) return []
  if (w.kind === 'approval') {
    return [
      { text: `Waiting on: approval by ${w.role ?? 'an approver'} (${w.gate ?? 'gate'})`, color: 'warning', bold: true },
      { text: `  The approver runs ${w.command}` },
    ]
  }
  if (w.kind === 'input') {
    return [
      { text: 'Waiting on: your answers', color: 'warning', bold: true },
      { text: `  Answer in ${w.file ?? 'open-questions.md'}, then ${w.command}` },
    ]
  }
  // Signed, not resumed yet: say what the decision was, never "approved" for a reject.
  const gate = w.gate ?? 'gate'
  const said: Record<string, Row> = {
    approve: { text: `Approved (${gate}): the run owner resumes`, color: 'success', bold: true },
    changes: { text: `Changes asked (${gate}): the run owner resumes; the step runs again`, color: 'warning', bold: true },
    reject: { text: `Rejected (${gate}): the run owner resumes to close the run`, color: 'error', bold: true },
    abort: { text: `Aborted (${gate}): the run owner resumes to close the run`, color: 'error', bold: true },
  }
  return [
    said[w.decision ?? ''] ?? { text: `Decided (${gate}): the run owner resumes`, bold: true },
    { text: `  ${w.command}` },
  ]
}

// Local HH:MM of a UTC timestamp from tsl, or null when it cannot be read.
function localTime(iso: string | null | undefined): string | null {
  const t = iso ? new Date(iso) : null
  if (!t || Number.isNaN(t.getTime())) return null
  return `${String(t.getHours()).padStart(2, '0')}:${String(t.getMinutes()).padStart(2, '0')}`
}

// How many of n items fit under a header in room rows, keeping one row for "…and N more".
function fits(n: number, room: number): number {
  return n <= room - 1 ? n : Math.max(0, room - 2)
}

// Asked in the chat right now (an AskUserQuestion dialog is open): answered there, not in a file.
function ideRows(p: Progress, room: number): Row[] {
  const items = p.questions.items.filter((it) => it.ask === 'ide')
  if (items.length === 0 || room < 1) return []
  const since = localTime(items[0]!.since)
  const out: Row[] = [{ text: `Waiting on you${since ? ` since ${since}` : ''}: answer in the chat`, color: 'warning', bold: true }]
  if (room < 2) return out
  const shown = items.slice(0, fits(items.length, room))
  for (const it of shown) out.push({ text: ` ${it.id} ${it.text}`, color: 'warning' })
  if (shown.length < items.length) out.push({ text: ` …and ${items.length - shown.length} more in the chat`, dim: true })
  return out
}

function questionRows(p: Progress, room: number): Row[] {
  const q = p.questions
  const total = q.open_blocking + q.open_non_blocking
  if (total === 0 || room < 1) return []
  const out: Row[] = [{ text: `Open questions: ${q.open_blocking} blocking, ${q.open_non_blocking} other`, bold: true }]
  if (room < 2) return out
  const items = q.items.filter((it) => it.ask !== 'ide').slice(0, fits(total, room))
  for (const it of items) {
    const who = it.ask ? ` (${it.ask})` : ''
    out.push({ text: ` ${it.id}${who} ${it.text}`, color: it.blocking ? 'warning' : undefined })
  }
  if (items.length < total) out.push({ text: ` …and ${total - items.length} more in open-questions.md`, dim: true })
  return out
}

// Everything the pane draws, as plain rows: tested under Node without the engine.
function panelRows(d: Panel, rows: number): Row[] {
  const p = d.progress
  if (!p) {
    return [
      { text: 'No run in this session.', dim: true },
      { text: 'Start one with /truminds:run or /truminds:resume; /truminds:status lists all runs.', dim: true },
    ]
  }
  const wf = p.workflow.split('@')[0]
  const pos = p.position ? `   step ${p.position.n} of ${p.position.of}` : ''
  const status = p.status === 'COMPLETED' ? `COMPLETED${p.end_reason ? ` (${p.end_reason})` : ''}` : p.status
  const out: Row[] = [{ text: `${p.ticket} · ${wf} · ${status}${pos}`, bold: true }]
  if (d.stale) out.push({ text: `as of ${d.at ?? '?'}: tsl did not answer the last refresh`, dim: true })
  const width = Math.max(10, ...p.steps.map((s) => s.id.length))
  const wait = waitingRows(p)
  // An open chat ask comes first: when the step list leaves no room for its questions, the
  // steps fold to one line (the current step and how many are done).
  const ideCount = p.questions.items.filter((it) => it.ask === 'ide').length
  const after = out.length + p.steps.length + (wait.length ? wait.length + 1 : 0)
  if (ideCount && rows - after - 2 < ideCount + 1 && p.steps.length > 1) {
    const done = p.steps.filter((s) => DONE.includes(s.status)).length
    const cur = p.steps.find((s) => s.id === p.current) ?? p.steps.find((s) => s.status === 'IN_PROGRESS')
    const tally = `${done} of ${p.steps.length} steps done`
    out.push(cur ? { ...stepRow(cur, p.current, width), text: `${stepRow(cur, p.current, width).text} · ${tally}` } : { text: tally, dim: true })
  } else {
    for (const s of p.steps) out.push(stepRow(s, p.current, width))
  }
  if (wait.length) out.push({ text: '' }, ...wait)
  const ide = ideRows(p, rows - out.length - 2)
  if (ide.length) out.push({ text: '' }, ...ide)
  const qs = questionRows(p, rows - out.length - 2)
  if (qs.length) out.push({ text: '' }, ...qs)
  return out
}

function clockTime(): string {
  const t = new Date()
  return `${String(t.getHours()).padStart(2, '0')}:${String(t.getMinutes()).padStart(2, '0')}`
}

// One refresh at a time; a call during one asks for one more after it, and gets the promise
// of the running one, so /tsl-panel waits for an answer instead of reading the old state.
let running: Promise<void> | undefined
let again = false
let poll: { cancel: () => void } | undefined
let openedFor: string | undefined // the run the pane was opened for unasked, once per run
let afterAnswer: { cancel: () => void } | undefined // the refresh shortly after a dialog returned

async function fetchOnce($: any): Promise<void> {
  let session = ''
  try {
    session = String(await $.session.id())
  } catch {
    session = ''
  }
  const argv = ['tsl', 'state', 'show', '--progress', '--json']
  if (session) argv.push('--session', session)
  let got: Progress | null | undefined | typeof NO_REPO
  try {
    const r = await $.process.run(argv, { timeoutMs: TSL_TIMEOUT_MS })
    got = parseProgress(r.stdout)
  } catch (err) {
    // tsl missing (not on PATH): stop calling it each turn. A time-out may pass, so retry.
    if (/ENOENT|not found|cannot find/i.test(String(err))) idle = true
    got = undefined
  }
  if (got === NO_REPO) {
    idle = true
    got = null
  }
  const p = got
  if (p === undefined) {
    await update($, panel, (d: Panel) => ({ ...d, stale: d.progress !== null }))
    return
  }
  await update($, panel, () => ({ progress: p, at: clockTime(), stale: false }))
  if (p && p.status === 'PAUSED_APPROVAL') {
    poll ??= $.clock.every(POLL_MS, () => void refresh($).catch(() => undefined))
  } else if (poll) {
    poll.cancel()
    poll = undefined
  }
  if (p && p.status !== 'COMPLETED' && openedFor !== p.run_id) {
    openedFor = p.run_id
    void $.ui.open({ id: PANE, title: TITLE }).catch(() => undefined)
  }
}

function refresh($: any): Promise<void> {
  if (running) {
    again = true
    return running
  }
  running = (async () => {
    try {
      do {
        again = false
        await fetchOnce($)
      } while (again)
    } catch {
      // a view: a failed refresh never reaches the session
    } finally {
      running = undefined
    }
  })()
  return running
}

// A refresh someone asked for (a tsl command, /tsl-panel, /tsl-gate, /truminds:...): try tsl
// again even after it said there is nothing here.
function wake($: any): Promise<void> {
  idle = false
  return refresh($)
}

// ---------------------------------------------------------------- /tsl-gate Display and argument passing only:
// tsl checks the role, writes the decision, signs and pushes. The comment goes to tsl on
// stdin, so nothing a person types is parsed by a shell. Where Mods are off, run `tsl gate`.

const DECISIONS = ['approve', 'changes', 'reject', 'abort']
const USAGE =
  'Usage (a decision word is needed to decide): /tsl-gate [run_id [--gate G] [approve|changes|reject|abort [comment]]]. A comment cannot start with a dash.'

type Env = { ok?: boolean; message?: string; next?: string | null; data?: any }

const ID = /^[A-Za-z0-9][A-Za-z0-9._-]*$/

type Parsed = { argv: string[]; stdin?: string; run?: string } | null

// `--gate G` may stand after the run id, after the decision word, or at the very end.
// Anything else after the decision is the comment. null means: show USAGE.
function parseArgs(args: string): Parsed {
  let rest = args.trim()
  let gate: string | undefined
  const take = (re: RegExp, keep: (m: RegExpMatchArray) => string): boolean => {
    const m = rest.match(re)
    if (!m) return false
    gate = m[m.length - 1]
    rest = keep(m).trim()
    return true
  }
  if (/^--gate(\s|$)/.test(rest)) return null // a gate needs a run id
  take(/^(\S+)\s+--gate\s+(\S+)(?=\s|$)/, (m) => m[1] + rest.slice(m[0].length)) ||
    take(/^(\S+\s+\S+)\s+--gate\s+(\S+)(?=\s|$)/, (m) => m[1] + rest.slice(m[0].length)) ||
    take(/^(\S+\s+\S+(?:\s[\s\S]*)?)\s--gate\s+(\S+)$/, (m) => m[1])
  if (gate !== undefined && !ID.test(gate)) return null
  if (/(^|\s)--gate$/.test(rest)) return null // --gate without a value
  const m = rest.match(/^(\S+)(?:\s+(\S+))?(?:\s+([\s\S]*))?$/)
  const argv = ['tsl', 'gate', '--json']
  let stdin: string | undefined
  if (m) {
    if (!ID.test(m[1])) return null
    argv.push(m[1])
    if (m[2]) {
      if (!DECISIONS.includes(m[2])) return null
      argv.push(m[2])
      // A comment that starts like an option is a mistyped option (--gate=G, -g, a long dash):
      // refuse it, or tsl would pick the gate itself and sign with that text as the comment.
      if (m[3] && /^[-\u2013\u2014]/.test(m[3].trim())) return null
      if (m[3] && m[3].trim()) {
        argv.push('--comment-file', '-')
        stdin = m[3]
      }
    }
  }
  if (gate) argv.push('--gate', gate)
  return { argv, stdin, run: m?.[1] }
}

// tsl writes the text (one renderer); this only adds the rows and the next step.
function render(env: Env, argsRun?: string): string {
  const d = env.data ?? {}
  let text = env.message ?? ''
  if (Array.isArray(d.waiting)) {
    if (d.waiting.length === 0) return 'No gates are waiting for your role.'
    const rows = d.waiting.map((r: any) => `${r.run_id}  ${r.ticket}  ${r.gate} (${r.role})  ${r.command}`)
    return `${text}\n${rows.join('\n')}`
  }
  if (env.ok && d.decision && d.resumable) text += `\nYou own this run: run /truminds:resume ${argsRun ?? d.run_id}`
  else if (env.ok && d.decision) text += '\nThe run owner now runs /truminds:resume to continue.'
  if (!env.ok && env.next) text += `\nNext: ${env.next}`
  return text
}

export const register: Register = (on) => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'tsl-gate',
      description: 'Decide on an approval gate (list, summary, or approve|changes|reject|abort)',
      argumentHint: '[run_id [approve|changes|reject|abort] [comment]]',
    })
    await $.command.register({
      name: 'tsl-panel',
      description: "Show this session's Truminds run: steps, bands, what it waits on, open questions",
    })
    const r = await next(e)
    void refresh($).catch(() => undefined) // never awaited: a slow tsl must not hold the session up
    return r
  })

  // /truminds:run and /truminds:resume call tsl while their prompt is built, not as a tool call,
  // so the end of every turn refreshes too.
  // Not in a repo without tsl runs: after E-REPO-01, or with no tsl, a turn costs no process.
  on('turn.complete', async ($, e, next) => {
    const r = await next(e)
    if (!idle) void refresh($).catch(() => undefined)
    return r
  })

  on('prompt.submit', async ($, e, next) => {
    const r = await next(e)
    if (/^\s*\/truminds:/.test(String((e as any).text ?? ''))) idle = false
    return r
  })

  for (const tool of SHELLS) {
    on('tool.call', { tool } as any, async ($: any, e: any, next: any) => {
      const r = await next(e)
      if (isTslCommand(e.command) || isUpdateCommand(e.command)) void wake($).catch(() => undefined)
      return r
    })
  }

  // A question asked in the chat: shown while its dialog is open, gone once it is answered. The
  // tool call's next() runs the PreToolUse hooks and then the dialog, so refresh after a short
  // wait (the hook has recorded it by then), when the dialog returns, and once more a short
  // wait later: the post-tool hook that marks it answered may not have run yet.
  const later = ($: any) => $.clock.after(ASK_REFRESH_MS, () => {
    if (!idle) void refresh($).catch(() => undefined)
  })
  on('tool.call', { tool: 'AskUserQuestion' } as any, async ($: any, e: any, next: any) => {
    afterAnswer?.cancel() // a new ask: the last one's late refresh is not needed
    afterAnswer = undefined
    const timer = idle ? undefined : later($)
    try {
      return await next(e)
    } finally {
      timer?.cancel()
      if (!idle) {
        void refresh($).catch(() => undefined)
        afterAnswer = later($)
      }
    }
  })

  on('command.run', { command: 'tsl-panel' }, async ($) => {
    await $.ui.open({ id: PANE, title: TITLE }) // asked: placed at any width
    await wake($)
    const d = await read($, panel)
    return { text: d.progress ? `${TITLE} pane opened.` : 'No run in this session yet; the pane fills when one starts.' }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const d = await read($, panel)
    const rows = panelRows(d, (e as any).props?.scroll?.bodyRows ?? 24)
    // Plain h() calls, not JSX, so the Node test can load this module (tests/).
    return h(
      Box,
      { flexDirection: 'column' },
      ...rows.map((r) =>
        h(Text, { color: r.color, dimColor: r.dim, bold: r.bold, wrap: 'truncate-end' }, r.text || ' '),
      ),
    ) as RenderElement
  })

  on('command.run', { command: 'tsl-gate' }, async ($, e) => {
    const p = parseArgs(String(e.args ?? ''))
    if (!p) return { text: USAGE }
    const { argv, stdin } = p
    try {
      const r = await $.process.run(argv, { stdin, timeoutMs: 120000 })
      const line = r.stdout.trim().split(/\r?\n/).filter(Boolean).pop() ?? ''
      let env: Env
      try {
        env = JSON.parse(line)
      } catch {
        return { text: `tsl gate failed (exit ${r.exitCode}): ${(r.stderr || r.stdout).slice(-300)}` }
      }
      void wake($).catch(() => undefined) // a decision changes what the panel shows
      return { text: render(env, p.run) }
    } catch (err) {
      return { text: `tsl could not be run (${String(err).slice(0, 200)}). Install tsl or run it yourself: tsl gate ...` }
    }
  })
}

import { parseProgress, isTslCommand, panelRows, register } from './reg.ts'
import assert from 'node:assert/strict'

const run = (over: any = {}): any => ({
  run_id: 'run_01', ticket: 'HMS-9', workflow: 'brownfield-change@1.2.0', status: 'RUNNING',
  end_reason: null, updated_at: 't', bound: true, current: 'impact', position: { n: 3, of: 4 },
  steps: [
    { id: 'req', kind: 'skill', status: 'DONE', attempt: 1, band: 'High' },
    { id: 'split', kind: 'skill', status: 'ACCEPTED', attempt: 2, band: 'Low' },
    { id: 'impact', kind: 'skill', status: 'IN_PROGRESS', attempt: 2, band: null },
    { id: 'pr', kind: 'pr', status: 'PENDING', attempt: null, band: null },
  ],
  waiting: null,
  questions: { open_blocking: 0, open_non_blocking: 0, items: [] },
  ...over,
})
const env = (data: any, ok = true) => JSON.stringify({ ok, message: 'm', data }) + '\n'
const texts = (d: any, rows = 40) => panelRows(d, rows).map((r: any) => r.text)

// parseProgress: the last stdout line is the envelope; anything unusable is undefined.
assert.equal(parseProgress('banner\n' + env({ progress: null })), null)
assert.equal(parseProgress(env({ progress: run() }))!.ticket, 'HMS-9')
assert.equal(parseProgress(''), undefined)
assert.equal(parseProgress('Traceback ...'), undefined)
assert.equal(parseProgress(env({ runs: [] })), undefined) // a tsl without --progress
assert.equal(parseProgress(JSON.stringify({ ok: false, code: 'E-RUN-04', data: {} })), undefined)
assert.equal(parseProgress(JSON.stringify({ ok: false, code: 'E-REPO-01', data: {} })), null)

// isTslCommand: the run loop's tsl calls, not words that merely contain "tsl".
for (const c of ['tsl next run_1 --json', 'cd x && tsl decide r s', 'tsl.exe verify', '(tsl review record r s)'])
  assert.equal(isTslCommand(c), true, c)
for (const c of ['ls tsl/', 'pytsl run', 'echo tsl-hook', 'cat tsl.yaml', undefined, 42])
  assert.equal(isTslCommand(c), false, String(c))

// panelRows: no run.
assert.match(texts({ progress: null, at: null, stale: false })[0]!, /No run in this session/)

// A running run: header, a band per finished step, the current step's attempt, pending dim.
let rows = panelRows({ progress: run(), at: '10:42', stale: false }, 40)
assert.equal(rows[0]!.text, 'HMS-9 · brownfield-change · RUNNING   step 3 of 4')
assert.match(rows[1]!.text, /^✓ req +High$/)
assert.equal(rows[1]!.color, 'success')
assert.match(rows[2]!.text, /^✓ split +Low$/)
assert.equal(rows[2]!.color, 'error')
assert.match(rows[3]!.text, /^▶ impact +attempt 2$/)
assert.equal(rows[4]!.text, '· pr')
assert.equal(rows[4]!.dim, true)
assert.equal(rows.length, 5)

// Stale: the last answer stays, marked with its time.
assert.match(texts({ progress: run(), at: '10:42', stale: true })[1]!, /^as of 10:42/)

// Paused for approval: who, which gate, the command.
let t = texts({ progress: run({ status: 'PAUSED_APPROVAL', waiting: { kind: 'approval', gate: 'G-escalate-impact-1', role: 'tech_lead', command: '/tsl-gate run_01', file: null } }), at: null, stale: false })
assert.ok(t.includes('Waiting on: approval by tech_lead (G-escalate-impact-1)'), t.join('\n'))
assert.ok(t.includes('  The approver runs /tsl-gate run_01'))

// Paused for input: the questions, blocking first as tsl sent them, cut to the room left.
const items = Array.from({ length: 6 }, (_, i) => ({ id: `Q-0${i + 1}`, blocking: i < 2, ask: 'product owner', text: `Question ${i + 1}?` }))
const input = run({ status: 'PAUSED_INPUT', waiting: { kind: 'input', gate: null, role: null, command: '/truminds:resume run_01', file: 'runs/run_01/open-questions.md' }, questions: { open_blocking: 2, open_non_blocking: 4, items } })
t = texts({ progress: input, at: null, stale: false })
assert.ok(t.includes('  Answer in runs/run_01/open-questions.md, then /truminds:resume run_01'), t.join('\n'))
assert.ok(t.includes('Open questions: 2 blocking, 4 other'))
assert.ok(t.includes(' Q-01 (product owner) Question 1?'))
assert.ok(t.includes(' Q-06 (product owner) Question 6?'))
const short = texts({ progress: input, at: null, stale: false }, 14)
assert.ok(short.some((x: string) => /…and \d more in open-questions.md/.test(x)), short.join('\n'))
assert.ok(!short.includes(' Q-06 (product owner) Question 6?'))
const blocking = panelRows({ progress: input, at: null, stale: false }, 40).find((r: any) => r.text.startsWith(' Q-01'))
assert.equal(blocking!.color, 'warning')

// Completed: its end reason, no waiting rows.
t = texts({ progress: run({ status: 'COMPLETED', end_reason: 'pr_opened', current: null, position: null }), at: null, stale: false })
assert.equal(t[0], 'HMS-9 · brownfield-change · COMPLETED (pr_opened)')

// End to end with a fake host: the hooks, the tsl call, the state, the pane.
const hooks: Record<string, any> = {}
register(((ev: string, ...r: any[]) => { hooks[ev + (r.length > 1 ? JSON.stringify(r[0]) : '')] = r[r.length - 1] }) as any)
const store = new Map<string, any>()
const calls: string[][] = []
const opened: string[] = []
const timers: any[] = []
let answer: () => Promise<any> = async () => ({ stdout: env({ progress: run() }), stderr: '', exitCode: 0 })
const $: any = {
  session: { id: async () => 'sess-1' },
  process: { run: async (argv: string[]) => { calls.push(argv); return answer() } },
  ui: {
    open: async (p: any) => { opened.push(p.id); return { isPlaced: true } },
    resolve: () => ({ Box: 'Box', Text: 'Text' }),
  },
  command: { register: async () => undefined },
  clock: { every: (_ms: number, fn: any) => { const t = { fn, cancelled: false, cancel() { t.cancelled = true } }; timers.push(t); return t } },
  __store: store,
}
const settle = () => new Promise((r) => setTimeout(r, 20))
const panelState = () => store.get('panel')

// session.start registers both commands, refreshes without waiting, opens the pane for a run.
await hooks['session.start']($, {}, async () => ({}))
await settle()
assert.deepEqual(calls[0], ['tsl', 'state', 'show', '--progress', '--json', '--session', 'sess-1'])
assert.equal(panelState().progress.run_id, 'run_01')
assert.deepEqual(opened, ['truminds-run'])

// Bash: tsl commands refresh, others do not. The pane is not opened again for the same run.
const bash = hooks['tool.call{"tool":"Bash"}']
await bash($, { command: 'ls' }, async () => ({}))
await settle()
assert.equal(calls.length, 1)
await bash($, { command: 'tsl next run_01 --json' }, async () => ({}))
await settle()
assert.equal(calls.length, 2)
assert.deepEqual(opened, ['truminds-run'])

// A slow or missing tsl: the hook returns at once, and the last answer stays, marked stale.
let release: () => void = () => undefined
answer = () => new Promise((_res, rej) => { release = () => rej(new Error('spawn tsl ENOENT')) })
const t0 = Date.now()
const res = await bash($, { command: 'tsl decide run_01 impact' }, async () => ({ ok: 1 }))
assert.deepEqual(res, { ok: 1 })
assert.ok(Date.now() - t0 < 50, 'the hook waited for tsl')
release()
await settle()
assert.equal(panelState().progress.run_id, 'run_01')
assert.equal(panelState().stale, true)

// One refresh at a time: calls during one fold into one more after it.
calls.length = 0
let finish: () => void = () => undefined
answer = () => new Promise((ok) => { finish = () => ok({ stdout: env({ progress: run() }), stderr: '', exitCode: 0 }) })
const turn = hooks['turn.complete']
for (let i = 0; i < 4; i++) await turn($, {}, async () => ({}))
await settle()
assert.equal(calls.length, 1)
finish()
await settle()
assert.equal(calls.length, 2)
finish()
await settle()
assert.equal(panelState().stale, false)

// Paused for approval starts the 30 s poll; leaving that state stops it.
answer = async () => ({ stdout: env({ progress: run({ status: 'PAUSED_APPROVAL' }) }), stderr: '', exitCode: 0 })
await turn($, {}, async () => ({}))
await settle()
assert.equal(timers.length, 1)
answer = async () => ({ stdout: env({ progress: run() }), stderr: '', exitCode: 0 })
await turn($, {}, async () => ({}))
await settle()
assert.equal(timers[0].cancelled, true)

// /tsl-panel opens the pane (asked: any width) and says what it shows.
const cmd = hooks['command.run{"command":"tsl-panel"}']
assert.deepEqual(await cmd($, { command: 'tsl-panel', args: '' }), { text: 'Truminds run pane opened.' })
answer = async () => ({ stdout: env({ progress: null }), stderr: '', exitCode: 0 })
assert.match((await cmd($, { command: 'tsl-panel', args: '' })).text, /No run in this session yet/)

// The pane draws one Text per row.
answer = async () => ({ stdout: env({ progress: run() }), stderr: '', exitCode: 0 })
await turn($, {}, async () => ({}))
await settle()
;(globalThis as any).h = (tag: any, props: any, ...children: any[]) => ({ tag, props, children })
const tree = await hooks['ui.render{"component":"Pane","requestId":"truminds-run"}']($, { viewport: { columns: 80, rows: 30 } })
assert.equal(tree.tag, 'Box')
assert.equal(tree.children.length, 5)
assert.equal(tree.children[1].props.color, 'success')
assert.equal(tree.children[1].props.wrap, 'truncate-end')

console.log('progress panel: all checks passed')

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
// Not a companion repo: a marker, so the end of each turn stops calling tsl here.
assert.equal(typeof parseProgress(JSON.stringify({ ok: false, code: 'E-REPO-01', data: {} })), 'symbol')

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

// Asked in the chat now (B2): first, with the local time it was asked and where to answer;
// the open-questions.md block still counts only that file's questions.
const at = new Date(2026, 10, 25, 9, 5).toISOString()
const ide = [
  { id: 'Q-01', blocking: true, ask: 'ide', since: at, text: 'Which window?' },
  { id: 'Q-02', blocking: true, ask: 'ide', since: at, text: 'Page size?' },
]
t = texts({ progress: run({ questions: { open_blocking: 0, open_non_blocking: 0, open_ide: 2, items: ide } }), at: null, stale: false })
assert.ok(t.includes('Waiting on you since 09:05: answer in the chat'), t.join('\n'))
assert.ok(t.includes(' Q-01 Which window?') && t.includes(' Q-02 Page size?'))
assert.ok(!t.some((x: string) => x.startsWith('Open questions')), 'no open-questions.md block')
const both = run({ questions: { open_blocking: 1, open_non_blocking: 0, open_ide: 1, items: [ide[0], items[0]] } })
t = texts({ progress: both, at: null, stale: false })
assert.ok(t.indexOf(' Q-01 Which window?') < t.indexOf('Open questions: 1 blocking, 0 other'), t.join('\n'))
assert.ok(t.includes(' Q-01 (product owner) Question 1?') && !t.includes(' Q-01 (ide) Which window?'))
assert.ok(texts({ progress: run({ questions: { open_blocking: 0, open_non_blocking: 0, items: [{ ...ide[0], since: 'x' }] } }), at: null, stale: false }).includes('Waiting on you: answer in the chat'))
// A short pane: the steps fold to one line so the chat questions show (validation note, 26 Nov).
const asking = { progress: run({ questions: { open_blocking: 0, open_non_blocking: 0, open_ide: 2, items: ide } }), at: null, stale: false }
t = texts(asking, 7)
assert.ok(t.some((x: string) => x.startsWith('▶ impact') && x.endsWith('· 2 of 4 steps done')), t.join('\n'))
assert.ok(t.includes(' Q-01 Which window?') && t.includes(' Q-02 Page size?') && !t.some((x: string) => x.startsWith('✓ req')), t.join('\n'))
assert.ok(texts(asking, 40).some((x: string) => x.startsWith('✓ req'))) // room for both: the full list
// Never more rows than the pane has: the header, what fits, and "…and N more" (review, 26 Nov).
const many = { progress: run({ steps: [run().steps[2]], questions: { open_blocking: 0, open_non_blocking: 0, open_ide: 5, items: [...ide, ...ide, ide[0]] } }), at: null, stale: false }
for (const n of [3, 4, 5, 6]) assert.ok(panelRows(many, n).length <= n, `${n}: ${texts(many, n).join(' | ')}`)
t = texts(many, 8)
assert.ok(t.includes(' …and 3 more in the chat') && t.includes(' Q-02 Page size?'), t.join('\n'))

// Signed, not resumed: the decision is said as it is; a reject is never shown as approved.
const resume = (decision: any) => texts({ progress: run({ status: 'PAUSED_APPROVAL', waiting: { kind: 'resume', gate: 'G-1', role: null, decision, command: '/truminds:resume run_01', file: null } }), at: null, stale: false })
assert.ok(resume('approve').includes('Approved (G-1): the run owner resumes'))
assert.ok(resume('reject').includes('Rejected (G-1): the run owner resumes to close the run'), resume('reject').join('\n'))
assert.ok(resume('changes').includes('Changes asked (G-1): the run owner resumes; the step runs again'))
assert.ok(resume('abort').includes('Aborted (G-1): the run owner resumes to close the run'))
assert.ok(resume(null).includes('Decided (G-1): the run owner resumes'))
for (const d of ['reject', 'changes', 'abort', null]) assert.ok(!resume(d).some((x: string) => x.startsWith('Approved')), String(d))

// A gate id longer than 10 characters keeps a space before its status.
t = texts({ progress: run({ steps: [{ id: 'G-threat-review', kind: 'gate', status: 'WAITING_APPROVAL', attempt: null, band: null }], current: null }), at: null, stale: false })
assert.ok(t.includes('⏸ G-threat-review waiting'), t.join('\n'))

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
const afters: any[] = []
let answer: () => Promise<any> = async () => ({ stdout: env({ progress: run() }), stderr: '', exitCode: 0 })
const $: any = {
  session: { id: async () => 'sess-1' },
  process: { run: async (argv: string[]) => { calls.push(argv); return answer() } },
  ui: {
    open: async (p: any) => { opened.push(p.id); return { isPlaced: true } },
    resolve: () => ({ Box: 'Box', Text: 'Text' }),
  },
  command: { register: async () => undefined },
  clock: {
    every: (_ms: number, fn: any) => { const t = { fn, cancelled: false, cancel() { t.cancelled = true } }; timers.push(t); return t },
    after: (ms: number, fn: any) => { const t = { ms, fn, cancelled: false, cancel() { t.cancelled = true } }; afters.push(t); return t },
  },
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

// A slow tsl: the hook returns at once, and the last answer stays, marked stale.
let release: () => void = () => undefined
answer = () => new Promise((_res, rej) => { release = () => rej(new Error('tsl timed out after 8000 ms')) })
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

// No tsl, or not a companion repo: the end of a turn stops calling tsl; a tsl command (Bash or
// PowerShell) or a /truminds: command tries again.
const ps = hooks['tool.call{"tool":"PowerShell"}']
assert.ok(ps, 'PowerShell tsl calls refresh too')
answer = async () => { throw new Error('spawn tsl ENOENT') }
await turn($, {}, async () => ({}))
await settle()
calls.length = 0
await turn($, {}, async () => ({}))
await settle()
assert.equal(calls.length, 0, 'tsl missing: turns stop calling it')
answer = async () => ({ stdout: env({ progress: run() }), stderr: '', exitCode: 0 })
await ps($, { command: 'tsl next run_01 --json' }, async () => ({}))
await settle()
assert.equal(calls.length, 1, 'a tsl call through PowerShell refreshes and wakes the panel')
await turn($, {}, async () => ({}))
await settle()
assert.equal(calls.length, 2)
answer = async () => ({ stdout: JSON.stringify({ ok: false, code: 'E-REPO-01', data: {} }) + '\n', stderr: '', exitCode: 2 })
await turn($, {}, async () => ({}))
await settle()
assert.equal(panelState().progress, null)
calls.length = 0
await turn($, {}, async () => ({}))
await settle()
assert.equal(calls.length, 0, 'not a companion repo: turns stop calling tsl')
await hooks['prompt.submit']($, { text: '/truminds:run HMS-9' }, async () => ({}))
answer = async () => ({ stdout: env({ progress: run() }), stderr: '', exitCode: 0 })
await turn($, {}, async () => ({}))
await settle()
assert.equal(calls.length, 1, '/truminds: wakes the panel')

// AskUserQuestion: a refresh once the pre-tool hook has recorded the question (the dialog is
// open, next() pending), and one when it returns; an early answer cancels the first.
const askHook = hooks['tool.call{"tool":"AskUserQuestion"}']
assert.ok(askHook, 'AskUserQuestion refreshes the panel')
calls.length = 0
let answerDialog: () => void = () => undefined
const asked = askHook($, { tool: 'AskUserQuestion' }, () => new Promise((ok) => { answerDialog = () => ok({ answers: 1 }) }))
assert.equal(afters.length, 1)
assert.equal(calls.length, 0, 'not before the hook has recorded it')
afters[0].fn()
await settle()
assert.equal(calls.length, 1, 'refreshed while the dialog is open')
answerDialog()
assert.deepEqual(await asked, { answers: 1 })
await settle()
assert.equal(calls.length, 2, 'refreshed when the dialog returned')
assert.equal(afters[0].cancelled, true)
assert.equal(afters.length, 2, 'and once more after the post-tool hook')
afters[1].fn()
await settle()
assert.equal(calls.length, 3)
// A new ask cancels the last one's late refresh (review of #74).
const again2 = askHook($, { tool: 'AskUserQuestion' }, async () => ({ answers: 2 }))
assert.equal(afters[1].cancelled, true)
await again2
await settle()

// /tsl-panel during a running refresh waits for its answer instead of reading the old state.
store.set('panel', { progress: null, at: null, stale: false })
let done: () => void = () => undefined
answer = () => new Promise((ok) => { done = () => ok({ stdout: env({ progress: run() }), stderr: '', exitCode: 0 }) })
await turn($, {}, async () => ({}))
const reply = hooks['command.run{"command":"tsl-panel"}']($, { command: 'tsl-panel', args: '' })
await settle()
done()
await settle()
done()
assert.deepEqual(await reply, { text: 'Truminds run pane opened.' })
answer = async () => ({ stdout: env({ progress: run() }), stderr: '', exitCode: 0 })

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
const pane = hooks['ui.render{"component":"Pane","requestId":"truminds-run"}']
const tree = await pane($, { props: { title: 'Truminds run', scroll: { offset: 0, bodyRows: 30 } } })
assert.equal(tree.tag, 'Box')
assert.equal(tree.children.length, 5)
// The pane's height comes from props.scroll.bodyRows: a short pane cuts the question list.
answer = async () => ({ stdout: env({ progress: input }), stderr: '', exitCode: 0 })
await turn($, {}, async () => ({}))
await settle()
const tall = await pane($, { props: { scroll: { offset: 0, bodyRows: 40 } } })
const low = await pane($, { props: { scroll: { offset: 0, bodyRows: 14 } } })
assert.ok(low.children.length < tall.children.length, `${low.children.length} < ${tall.children.length}`)
assert.ok(low.children.some((c: any) => /…and \d more/.test(c.children[0])))
assert.equal(tree.children[1].props.color, 'success')
assert.equal(tree.children[1].props.wrap, 'truncate-end')

console.log('progress panel: all checks passed')

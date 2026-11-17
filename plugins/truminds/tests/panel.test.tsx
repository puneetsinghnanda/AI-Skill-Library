// Engine-level test of the progress panel: `claude plugin test plugins/truminds`.
// Local only (CI has no Claude Code); the logic is also covered under Node by
// test_tsl_gate_mod.py, which CI runs.
import { expect, test } from 'claude-code/testing'

const PANE = {
  plugin: 'truminds',
  component: 'Pane',
  requestId: 'truminds-run',
  props: {
    title: 'Truminds run',
    isFocused: false,
    bodyColumns: 60,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 30 },
    view: {},
  },
} as const

const run = (over: Record<string, unknown> = {}) => ({
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

const answer = (progress: unknown) => ({
  value: { stdout: JSON.stringify({ ok: true, message: 'm', data: { progress } }) + '\n', stderr: '', exitCode: 0 },
})

function engine(on: any, progress: () => unknown, argvSeen: string[][] = [], opened: string[] = []) {
  on('command.register', (_: any, e: any) => ({ value: { command: e.name } }))
  on('ui.open', (_: any, e: any) => {
    opened.push(e.id)
    return { value: { isPlaced: true } }
  })
  on('session.start', (_: any, e: any) => ({ cwd: e.cwd }))
  on('session.id', () => ({ value: 'sess-1' }))
  on('clock.every', () => ({ value: { cancel() {} } }))
  on('process.run', (_: any, e: any) => {
    argvSeen.push(e.argv)
    return answer(progress())
  })
}

const flush = () => new Promise((r) => setTimeout(r, 50))

test('a running run: steps with bands and the current attempt, on terminal and desktop', async ($, on) => {
  const seen: string[][] = []
  engine(on, () => run(), seen)
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  await flush()
  expect(seen[0]).toEqual(['tsl', 'state', 'show', '--progress', '--json', '--session', 'sess-1'])
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })
    expect((await ui.find({ type: 'Text', text: /^HMS-9/ }))?.text).toBe(
      'HMS-9 · brownfield-change · RUNNING   step 3 of 4',
    )
    expect((await ui.find({ type: 'Text', text: /req/ }))?.text).toMatch(/High$/)
    expect((await ui.find({ type: 'Text', text: /split/ }))?.text).toMatch(/Low$/)
    expect((await ui.find({ type: 'Text', text: /impact/ }))?.text).toMatch(/attempt 2$/)
    await ui.unmount()
  }
})

test('paused for approval names the approver and the command', async ($, on) => {
  engine(on, () =>
    run({
      status: 'PAUSED_APPROVAL',
      waiting: { kind: 'approval', gate: 'G-escalate-impact-1', role: 'tech_lead', command: '/tsl-gate run_01', file: null },
    }),
  )
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  await flush()
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })
    expect((await ui.find({ type: 'Text', text: /Waiting on/ }))?.text).toBe(
      'Waiting on: approval by tech_lead (G-escalate-impact-1)',
    )
    expect((await ui.find({ type: 'Text', text: /tsl-gate/ }))?.text).toBe('  The approver runs /tsl-gate run_01')
    await ui.unmount()
  }
})

test('paused for input lists the open questions', async ($, on) => {
  engine(on, () =>
    run({
      status: 'PAUSED_INPUT',
      waiting: { kind: 'input', gate: null, role: null, command: '/truminds:resume run_01', file: 'runs/run_01/open-questions.md' },
      questions: {
        open_blocking: 1,
        open_non_blocking: 1,
        items: [
          { id: 'Q-01', blocking: true, ask: 'product owner', text: 'Keep 24 hours or 30 days?' },
          { id: 'Q-02', blocking: false, ask: 'tech lead', text: 'Index the history table?' },
        ],
      },
    }),
  )
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  await flush()
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })
    expect((await ui.find({ type: 'Text', text: /Open questions/ }))?.text).toBe('Open questions: 1 blocking, 1 other')
    expect((await ui.find({ type: 'Text', text: /Q-01/ }))?.text).toBe(' Q-01 (product owner) Keep 24 hours or 30 days?')
    await ui.unmount()
  }
})

test('no run in this session, and tsl missing, show the empty line', async ($, on) => {
  on('command.register', (_: any, e: any) => ({ value: { command: e.name } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('session.start', (_: any, e: any) => ({ cwd: e.cwd }))
  on('session.id', () => ({ value: 'sess-1' }))
  on('process.run', () => {
    throw new Error('spawn tsl ENOENT')
  })
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  await flush()
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ ...PANE, surface })
    expect((await ui.find({ type: 'Text', text: /No run/ }))?.text).toBe('No run in this session.')
    await ui.unmount()
  }
})

test('/tsl-panel opens the pane', async ($, on) => {
  const opened: string[] = []
  engine(on, () => null, [], opened)
  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  await flush()
  expect(opened).toEqual([]) // no run: never opened unasked
  const r = await $.command.run({ command: 'tsl-panel', args: '' })
  expect(opened).toContain('truminds-run')
  expect((r as any).text).toMatch(/No run in this session yet/)
})

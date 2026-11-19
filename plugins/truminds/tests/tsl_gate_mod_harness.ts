import { parseArgs, render, register } from './reg.ts'
import assert from 'node:assert/strict'
const a = (s: string) => { const p = parseArgs(s); return p ? [p.argv.slice(3).join(' '), p.stdin] : null }
assert.deepEqual(a(''), ['', undefined])
assert.deepEqual(a('R1'), ['R1', undefined])
assert.deepEqual(a('R1 approve'), ['R1 approve', undefined])
assert.deepEqual(a('R1 approve --gate W-1'), ['R1 approve --gate W-1', undefined])
assert.deepEqual(a('R1 --gate W-1 approve'), ['R1 approve --gate W-1', undefined])
assert.deepEqual(a('R1 --gate W-1'), ['R1 --gate W-1', undefined])
assert.deepEqual(a('R1 changes rename X --gate W-1'), ['R1 changes --comment-file - --gate W-1', 'rename X'])
assert.deepEqual(a('R1 changes --gate G-req rename "X" $HOME'), ['R1 changes --comment-file - --gate G-req', 'rename "X" $HOME'])
assert.deepEqual(a('R1 --gate G-req changes two\nlines'), ['R1 changes --comment-file - --gate G-req', 'two\nlines'])
assert.deepEqual(a('R1 changes use the --gate flag in docs please'), ['R1 changes --comment-file -', 'use the --gate flag in docs please'])
assert.equal(a('R1 approve --gate'), null)
assert.equal(a('--gate W-1'), null)
assert.equal(a('R1 approve --gate W;1'), null)
for (const bad of ['--gate=W-1', '\u2014gate W-1', '-g W-1', '--Gate W-1', '--resign', '- x']) assert.equal(a(`R1 approve ${bad}`), null, bad)
assert.deepEqual(a('R1 changes not - this'), ['R1 changes --comment-file -', 'not - this'])
assert.equal(a('R1 maybe'), null)
assert.equal(a('R;1 approve'), null)
assert.equal(a('R1 approve --gate --resign'), null)
// render
assert.equal(render({ ok: true, message: 'L1\nYou do not hold the tech_lead role\nDecide: x', data: { gate: 'G', portal: 'p', run_id: 'R1' } }), 'L1\nYou do not hold the tech_lead role\nDecide: x')
assert.equal(render({ ok: true, message: '0 gates waiting for you', data: { waiting: [] } }), 'No gates are waiting for your role.')
assert.match(render({ ok: true, message: '1 gate', data: { waiting: [{ run_id: 'R1', ticket: 'T', gate: 'W-1', role: 'tech_lead', command: '/tsl-gate R1' }] } }), /R1  T  W-1 \(tech_lead\)/)
assert.match(render({ ok: true, message: 'G approve signed', data: { decision: 'approve', resumable: true, run_id: 'R1' } }, 'R1'), /resume R1/)
assert.match(render({ ok: false, message: 'bad', next: 'do x', data: {} }), /Next: do x/)
// end to end with a fake host
const reg: any = {}; register(((ev: string, ...r: any[]) => { reg[ev] = r[r.length - 1] }) as any)
let seen: any
// Only the tsl gate call: a decision also starts a panel refresh (tsl state show --progress).
const $ = { process: { run: async (argv: string[], o: any) => { if (argv[1] === 'gate') seen = [argv, o.stdin]; return { stdout: JSON.stringify({ ok: true, message: 'm', data: {} }) + '\n', stderr: '', exitCode: 0 } } } }
assert.deepEqual(await reg['command.run']($, { args: 'R1 approve --gate W-1' }), { text: 'm' })
assert.deepEqual(seen, [['tsl', 'gate', '--json', 'R1', 'approve', '--gate', 'W-1'], undefined])
assert.match((await reg['command.run']($, { args: 'R1 nope' })).text, /^Usage/)
console.log('register.tsx: all checks passed')

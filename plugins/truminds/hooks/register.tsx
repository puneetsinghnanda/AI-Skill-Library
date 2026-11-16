import type { Register } from 'claude-code'

// /tsl-gate - decide on an approval gate. Display and argument passing only:
// tsl checks the role, writes the decision, signs and pushes. The comment goes to tsl on
// stdin, so nothing a person types is parsed by a shell. Where Mods are off, run `tsl gate`.

const DECISIONS = ['approve', 'changes', 'reject', 'abort']
const USAGE =
  'Usage (a decision word is needed to decide): /tsl-gate [run_id [--gate G] [approve|changes|reject|abort [comment]]]'

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
    return next(e)
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
      return { text: render(env, p.run) }
    } catch (err) {
      return { text: `tsl could not be run (${String(err).slice(0, 200)}). Install tsl or run it yourself: tsl gate ...` }
    }
  })
}

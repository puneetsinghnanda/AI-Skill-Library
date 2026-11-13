import type { Register } from 'claude-code'

// /tsl-gate - decide on an approval gate. Display and argument passing only:
// tsl checks the role, writes the decision, signs and pushes. The comment goes to tsl on
// stdin, so nothing a person types is parsed by a shell. Where Mods are off, run `tsl gate`.

const DECISIONS = ['approve', 'changes', 'reject', 'abort']
const USAGE = 'Usage: /tsl-gate [run_id [approve|changes|reject|abort [comment]]]  [--gate G]'

type Env = { ok?: boolean; message?: string; next?: string | null; data?: any }

function render(env: Env, argsRun?: string): string {
  const d = env.data ?? {}
  if (Array.isArray(d.waiting)) {
    if (d.waiting.length === 0) return 'No gates are waiting for your role.'
    const rows = d.waiting.map((r: any) => `${r.run_id}  ${r.ticket}  ${r.gate} (${r.role})  ${r.command}`)
    return `${env.message}\n${rows.join('\n')}`
  }
  let text = env.message ?? ''
  if (env.ok && d.gate && d.portal && !d.decision) {
    text = [
      `Gate ${d.gate} on ${d.run_id} (${d.ticket}, ${d.workflow})`,
      `Needs role: ${d.role}`,
      d.reason ? `Why: ${d.reason}` : '',
      ...(d.artifacts ?? []).map((a: string) => `Artifact: ${a}`),
      `Details: ${d.portal}`,
      `Decide: /tsl-gate ${d.run_id} approve|changes|reject|abort [comment]`,
    ].filter(Boolean).join('
')
    return text
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
    let rest = String(e.args ?? '').trim()
    let gate: string | undefined
    const g = rest.match(/(^|\s)--gate\s+(\S+)/)
    if (g) {
      gate = g[2]
      rest = rest.replace(g[0], ' ').trim()
    }
    const m = rest.match(/^(\S+)(?:\s+(\S+))?(?:\s+([\s\S]*))?$/)
    const argv = ['tsl', 'gate', '--json']
    let stdin: string | undefined
    if (m) {
      argv.push(m[1])
      if (m[2]) {
        if (!DECISIONS.includes(m[2])) return { text: USAGE }
        argv.push(m[2])
        if (m[3] && m[3].trim()) {
          argv.push('--comment-file', '-')
          stdin = m[3]
        }
      }
    }
    if (gate) argv.push('--gate', gate)
    try {
      const r = await $.process.run(argv, { stdin, timeoutMs: 120000 })
      const line = r.stdout.trim().split(/\r?\n/).filter(Boolean).pop() ?? ''
      let env: Env
      try {
        env = JSON.parse(line)
      } catch {
        return { text: `tsl gate failed (exit ${r.exitCode}): ${(r.stderr || r.stdout).slice(-300)}` }
      }
      return { text: render(env, m?.[1]) }
    } catch (err) {
      return { text: `tsl could not be run (${String(err).slice(0, 200)}). Install tsl or run it yourself: tsl gate ...` }
    }
  })
}

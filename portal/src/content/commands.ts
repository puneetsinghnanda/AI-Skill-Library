/**
 * Command strings shown on screens must match Doc 5 §2 and the registry §3 (SDD-09 §4.5).
 * `content/commands.test.ts` checks every command used in content/ against these lists, and checks
 * each `/truminds:*` command against the plugin's skill folders (plugins/truminds/skills/<name>).
 */

/** `tsl` commands (registry §3.1). */
export const TSL_COMMANDS = [
  'tsl login',
  'tsl logout',
  'tsl whoami',
  'tsl keys',
  'tsl doctor',
  'tsl init',
  'tsl validate',
  'tsl verify',
  'tsl state start',
  'tsl state resume',
  'tsl state show',
  'tsl state unlock',
  'tsl next',
  'tsl review',
  'tsl decide',
  'tsl approve',
  'tsl pr',
  'tsl ci-verify',
  'tsl context build',
  'tsl context sign',
  'tsl context status',
  'tsl eval',
  'tsl improve',
  'tsl events flush',
  'tsl migrate',
  'tsl companion',
] as const;

/** Plugin slash commands (registry §3.2); each is a skill folder in plugins/truminds/skills. */
export const SLASH_COMMANDS = [
  '/truminds:run',
  '/truminds:resume',
  '/truminds:status',
  '/truminds:eval',
  '/truminds:improve',
  '/truminds:context-draft',
] as const;

/** Claude Code built-in plugin commands (development seats only, DEV-01 §5). */
export const CLAUDE_CODE_COMMANDS = ['/plugin marketplace add', '/plugin install'] as const;

export const RUN_TEMPLATE = '/truminds:run <workflow> <ticket>';

export function runCommand(workflow: string | null | undefined, ticket = '<ticket>'): string {
  return `/truminds:run ${workflow || '<workflow>'} ${ticket}`;
}

/** True when `cmd` starts with a known command (tsl, slash, Claude Code, git or uv). */
export function isKnownCommand(cmd: string): boolean {
  const c = cmd.trim();
  if (c.startsWith('git clone ') || c.startsWith('uv tool install ')) return true;
  return [...TSL_COMMANDS, ...SLASH_COMMANDS, ...CLAUDE_CODE_COMMANDS].some(
    (k) => c === k || c.startsWith(`${k} `),
  );
}

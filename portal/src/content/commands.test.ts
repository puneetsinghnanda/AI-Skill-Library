/** SDD-09 §4.5: command strings on screens match Doc 5 §2 and the plugin (registry §3). */
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { RUN_TEMPLATE, SLASH_COMMANDS, isKnownCommand } from './commands';
import { BUSINESS_STEPS, developmentSeatCommands, engineerSteps } from './get-started';
import { STEPS } from './how-it-works';

const skillsDir = resolve(__dirname, '../../../plugins/truminds/skills');
const all = [
  RUN_TEMPLATE,
  ...STEPS.flatMap((s) => s.commands),
  ...engineerSteps('1.6.0').flatMap((s) => s.commands),
  ...developmentSeatCommands('demo-org/truminds-skill-library'),
];

describe('commands shown on screens', () => {
  it.each(all)('"%s" is a known command', (cmd) => {
    expect(isKnownCommand(cmd)).toBe(true);
  });

  it.each(SLASH_COMMANDS)('%s is a skill folder in plugins/truminds/skills', (cmd) => {
    const name = cmd.replace('/truminds:', '');
    expect(existsSync(resolve(skillsDir, name, 'SKILL.md'))).toBe(true);
  });

  it('every /truminds: command used on a screen is in the plugin', () => {
    const used = all.flatMap((c) => c.match(/\/truminds:[a-z-]+/g) ?? []);
    expect(used.length).toBeGreaterThan(0);
    for (const u of used) expect(SLASH_COMMANDS).toContain(u);
  });

  it('the business steps carry no commands', () => {
    expect(JSON.stringify(BUSINESS_STEPS)).not.toMatch(/tsl |\/truminds:/);
  });

  it('get started does not tell company seats to install the plugin by hand (SDD-13 §3.4)', () => {
    expect(
      engineerSteps('1.6.0')
        .flatMap((s) => s.commands)
        .some((c) => c.startsWith('/plugin')),
    ).toBe(false);
  });
});

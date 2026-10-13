/**
 * Get started (board GetStarted; SDD-09 §4.8, Doc 4 §2.0.2, SDD-13 §3). The plugin is not installed
 * by hand: managed settings force-enable it on company seats (SDD-05 §6.2, SDD-13 §3.4). Manual
 * marketplace steps appear only in the collapsed "Development seats only" note (DEV-01 §5).
 * `[TRUMINDS-ORG]` placeholders come from VITE_MARKETPLACE_REPO_URL (OQ-10).
 */
export interface EngineerStep {
  title: string;
  desc: string;
  commands: string[];
}

export function engineerSteps(pluginVersion: string | null): EngineerStep[] {
  const v = pluginVersion ?? 'X.Y.Z';
  return [
    {
      title: 'Install tsl',
      desc: `Download the tsl wheel and SHA256SUMS from release v${v} of the Skill Library repository, check the hash, then install it. If the hashes differ, stop and tell the release maintainer.`,
      commands: [`uv tool install --python 3.12 ./truminds_tsl-${v}-py3-none-any.whl`],
    },
    {
      title: 'Sign in and register your key',
      desc: 'Signs you in with company SSO and registers the key that signs your check records. Run it in a terminal yourself, not through Claude.',
      commands: ['tsl login'],
    },
    {
      title: 'Check your laptop',
      desc: 'Every check must pass: python, uv, git, Docker, version, keychain, login and the service.',
      commands: ['tsl doctor'],
    },
    {
      title: 'Confirm the plugin is enabled',
      desc: 'Managed settings install the Truminds plugin on every company seat. In the Claude Code desktop app, start a Local session and type the command below. Any reply from tsl, even "no runs", means you are set up.',
      commands: ['/truminds:status'],
    },
    {
      title: "Open the client system's companion repo and start a run",
      desc: 'Clone the companion repo your tech lead set up; it holds the context pack and run records. Pick a workflow and a ticket. Answer questions when the run pauses, then resume.',
      commands: [
        'git clone git@github.com:<companion-org>/<system>-companion.git',
        '/truminds:run <workflow> <ticket>',
      ],
    },
  ];
}

export function developmentSeatCommands(repoSlug: string): string[] {
  return [
    `/plugin marketplace add ${repoSlug}`,
    `/plugin install truminds@${repoSlug.split('/').pop() ?? 'truminds-skill-library'}`,
  ];
}

export const BEFORE_YOU_START = [
  'Company Claude seat (never a personal account)',
  'Claude Code desktop app',
  'Company SSO and GitHub access',
  'Python 3.12, uv, git and Docker, for build and test checks',
  'Client consent recorded by an admin',
];

export const BUSINESS_STEPS: {
  title: string;
  text: string;
  link?: { to: string; label: string };
}[] = [
  {
    title: 'Share what we can do',
    text: 'Open the capability map and the pod catalogue in a client meeting. Everything shown is client-safe.',
    link: { to: '/insights', label: 'Capability map →' },
  },
  {
    title: 'Propose a pod',
    text: 'Pick the pod that matches the engagement and download its one-pager for the proposal.',
    link: { to: '/pods', label: 'Pods →' },
  },
  {
    title: 'Get written consent',
    text: 'The client agrees in writing before any of their code is processed. The admin records it.',
  },
  {
    title: 'Hand over to delivery',
    text: 'The delivery manager and tech lead onboard the client system and start the pod.',
  },
];

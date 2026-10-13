/**
 * How it works (board HowItWorks; SDD-09 §4.5, Doc 4 §2.0.2). Commands use the registry names
 * (`tsl init`, `tsl context build`, ...), not the older prototype spellings.
 */
export interface FlowItem {
  title: string;
  hint: string;
  highlight?: boolean;
}

export const FLOW: FlowItem[] = [
  { title: '1 · Context pack', hint: 'what the system is' },
  { title: '2 · Workflow or pod', hint: 'which steps, which roles' },
  { title: '3 · Skills run', hint: 'in Claude Code' },
  { title: '4 · Harness checks', hint: 'after every step', highlight: true },
  { title: '5 · Human gates', hint: 'people decide' },
  { title: '6 · Pull request', hint: 'with proof attached' },
  { title: '7 · Insights', hint: 'learn and improve' },
];

export interface StepCard {
  title: string;
  who: string;
  desc: string;
  commands: string[];
  client: string;
}

export const STEPS: StepCard[] = [
  {
    title: 'Onboard the client system',
    who: 'Tech lead · Admin',
    desc: 'The tech lead builds the context pack from the real code (modules, APIs, data model) and signs it. Admin records written client consent and assigns company seats.',
    commands: ['tsl init', 'tsl context build', 'tsl context sign'],
    client:
      'A one-time setup per client system; the client agrees in writing before any code is used.',
  },
  {
    title: 'Choose a workflow or a pod',
    who: 'Engineer · Delivery manager',
    desc: 'Pick from the catalogue, for example the brownfield-change workflow or the Brownfield Change Pod. The Truminds plugin is already installed and enabled on every company seat.',
    commands: ['/truminds:status'],
    client: 'The pod you proposed decides which AI roles and workflows the team uses.',
  },
  {
    title: 'Run it in Claude Code',
    who: 'Engineer',
    desc: "Skills run one after another on the engineer's laptop. Client code stays in the engineer's tools and the client's repositories.",
    commands: ['/truminds:run <workflow> <ticket>'],
    client: "Work starts from the client's own ticket.",
  },
  {
    title: 'Every step is checked',
    who: 'Quality harness, automatic',
    desc: 'Code checks the facts, an AI reviewer checks the meaning against the context pack with citations, then code verifies the citations and decides the outcome and confidence.',
    commands: ['tsl verify <artifact>', 'tsl decide <artifact>'],
    client: 'Nothing moves on without passing checks; low confidence goes to a person.',
  },
  {
    title: 'People decide at gates',
    who: 'Product owner · Tech lead',
    desc: 'Open questions and approvals are written to a file; the run pauses until people answer. Every decision is signed and recorded.',
    commands: ['tsl approve <run_id> <gate>', '/truminds:resume <run_id>'],
    client: "The client's product owner answers business questions; nothing is guessed.",
  },
  {
    title: 'Pull request with proof',
    who: 'Engineer · Reviewer',
    desc: 'The pull request carries the code, unit-test results and the check record of every step. CI re-checks; a person reviews and merges. Nothing merges or deploys by itself.',
    commands: ['tsl pr <run_id>'],
    client: 'The client sees a normal pull request with an audit trail attached.',
  },
  {
    title: 'Insights and self-improvement',
    who: 'Skill owner · Eng lead · Business',
    desc: 'Only metadata reaches this portal. Weak skills are found from evidence; owners add a failing test case first, then improve the skill.',
    commands: ['/truminds:improve <skill>'],
    client: 'Quality improves release by release, and the numbers are shareable.',
  },
];

export const OUTCOMES: {
  outcome: 'PASS' | 'PASS-WITH-FINDINGS' | 'RETRY' | 'NEEDS-INPUT' | 'ESCALATE' | 'ABORT';
  text: string;
}[] = [
  { outcome: 'PASS', text: 'Next step starts.' },
  { outcome: 'PASS-WITH-FINDINGS', text: 'Continues; notes go to the PR.' },
  { outcome: 'RETRY', text: 'AI fixes it, at most 2 or 3 times.' },
  { outcome: 'NEEDS-INPUT', text: 'Questions file; run pauses.' },
  { outcome: 'ESCALATE', text: 'Tech lead approves or rejects.' },
  { outcome: 'ABORT', text: 'Stops: secrets, personal data or a blocked action.' },
];

export const WHERE: { title: string; text: string }[] = [
  {
    title: "Engineer's laptop",
    text: 'Claude Code desktop app with the Truminds plugin, on company Claude seats. The only place AI runs.',
  },
  {
    title: 'Companion repo, one per client system',
    text: "Context pack, run state, artifacts and signed check records. The client's product repo only receives code and pull requests.",
  },
  {
    title: 'This portal, on the intranet',
    text: 'Catalogue, pods and insights from metadata only: no code, no prompts, no client names. It shows status; it never runs AI.',
  },
];

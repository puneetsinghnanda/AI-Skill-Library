const pptxgen = require('pptxgenjs');
const { applyTheme } = require('/root/.claude/skills/synced/0764110e-bcdd-4a4e-8204-7d881be41967_8068bf98-8d88-4bcc-b260-c3c7b26ba1c4/pptx/scripts/apply_theme.js');

const THEME = {
  name: 'Truminds Skill Library',
  headFontFace: 'Calibri',
  bodyFontFace: 'Calibri',
  colors: {
    dk1: '0F1B2D', lt1: 'FFFFFF', dk2: '0B2A4A', lt2: 'F2F5F9',
    accent1: '00707B', accent2: '00A3B4', accent3: 'C2620F', accent4: '1B7A4E', accent5: '2458C6', accent6: '8A5A00',
    hlink: '00707B', folHlink: '2458C6'
  }
};

(async () => {
  const pres = new pptxgen();
  pres.layout = 'LAYOUT_16x9'; // 10 x 5.625
  pres.title = 'Truminds AI Skill Library - Architecture walkthrough';
  pres.author = 'Puneet Singh Nanda';
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  const C = pres.SchemeColor;
  const S = pres.shapes;

  pres.defineSlideMaster({
    title: 'DARK',
    background: { color: C.text2 },
    objects: [
      { placeholder: { options: { name: 'title', type: 'title', x: 0.6, y: 1.5, w: 8.8, h: 1.6, fontSize: 38, bold: true, color: C.background1, valign: 'bottom', align: 'left' }, text: '' } },
      { placeholder: { options: { name: 'body', type: 'body', x: 0.6, y: 3.25, w: 8.8, h: 1.0, fontSize: 16, color: C.background1, valign: 'top' }, text: '' } }
    ]
  });
  pres.defineSlideMaster({
    title: 'CONTENT',
    background: { color: C.background1 },
    objects: [
      { placeholder: { options: { name: 'title', type: 'title', x: 0.5, y: 0.28, w: 9.0, h: 0.62, fontSize: 28, bold: true, color: C.text2, valign: 'middle', margin: 0, align: 'left' }, text: '' } },
      { text: { text: 'Truminds AI Skill Library · Architecture walkthrough', options: { x: 0.5, y: 5.25, w: 6, h: 0.25, fontSize: 9, color: '5B6B80', margin: 0 } } }
    ],
    slideNumber: { x: 9.1, y: 5.25, w: 0.4, h: 0.25, fontSize: 9, color: '5B6B80', align: 'right' }
  });

  const tb = (slide, text, o) => slide.addText(text, Object.assign({ isTextBox: true, margin: 0, fontSize: 14, color: C.text1, valign: 'top' }, o));
  const box = (slide, o) => slide.addShape(S.ROUNDED_RECTANGLE, Object.assign({ rectRadius: 0.08, line: { color: 'DDE3EA', width: 1 }, fill: { color: C.background1 } }, o));
  const arrow = (slide, x, y, w, h, o = {}) => slide.addShape(S.LINE, Object.assign({ x, y, w, h, line: { color: '7A8799', width: 1.5, endArrowType: 'triangle' } }, o));
  const circleNum = (slide, n, x, y, d = 0.42, fill = C.text2) => {
    slide.addShape(S.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { color: fill, width: 0 } });
    tb(slide, String(n), { x, y, w: d, h: d, fontSize: 14, bold: true, color: C.background1, align: 'center', valign: 'middle' });
  };

  // 1. Title
  pres.addSection({ title: 'Intro' });
  let s = pres.addSlide({ masterName: 'DARK', sectionTitle: 'Intro' });
  s.addText('Truminds AI Skill Library', { placeholder: 'title' });
  s.addText('Architecture and end-to-end flow · team walkthrough', { placeholder: 'body' });
  s.addNotes('Goal of the session: everyone leaves knowing the core components, how one ticket flows end to end, and what they own next.');

  // 2. What we are building
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Intro' });
  s.addText('What we are building', { placeholder: 'title' });
  tb(s, 'Small reusable AI skills, chained into workflows and packaged as pods, with a quality check after every step', { x: 0.5, y: 0.95, w: 9, h: 0.5, fontSize: 15, color: '4F5E72' });
  const blocks = [
    ['Skill', 'One small AI capability, e.g. requirement review, design, unit tests. Technology- and domain-agnostic.'],
    ['Workflow', 'Skills in order with human gates, e.g. brownfield-change: requirement → design → code → PR.'],
    ['Pod', 'A ready-made AI-augmented team, e.g. 1 Solution Architect + 1 Full-stack + 1 QA agent.'],
    ['Harness', 'Checks every output against the client system, scores confidence, stops for a human when needed.']
  ];
  blocks.forEach((b, i) => {
    const x = 0.5 + i * 2.3;
    box(s, { x, y: 1.6, w: 2.1, h: 2.15, fill: { color: C.background2 }, line: { color: C.background2, width: 0 } });
    circleNum(s, i + 1, x + 0.18, 1.78, 0.42, i === 3 ? C.accent1 : C.text2);
    tb(s, b[0], { x: x + 0.18, y: 2.3, w: 1.8, h: 0.35, fontSize: 17, bold: true, color: C.text2 });
    tb(s, b[1], { x: x + 0.18, y: 2.68, w: 1.78, h: 0.95, fontSize: 11.5, color: C.text1 });
  });
  const rules = ['Runs locally in Claude Code desktop + Truminds plugin', 'Company Claude seats only · no Claude API', 'Any domain, greenfield or brownfield', 'People decide; code makes pass/fail decisions'];
  rules.forEach((r, i) => {
    const x = 0.5 + (i % 2) * 4.55, y = 4.0 + Math.floor(i / 2) * 0.55;
    s.addShape(S.OVAL, { x, y: y + 0.09, w: 0.16, h: 0.16, fill: { color: C.accent2 }, line: { color: C.accent2, width: 0 } });
    tb(s, r, { x: x + 0.28, y, w: 4.1, h: 0.36, fontSize: 13.5, valign: 'middle' });
  });
  s.addNotes('Seven objects in the design: skill, agent, workflow, pod, knowledge pack, artifact, verifier profile. Today we focus on skill, workflow, pod and harness.');

  // 3. Core components (five planes)
  pres.addSection({ title: 'Architecture' });
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Architecture' });
  s.addText('Core components: five planes, AI runs in only one', { placeholder: 'title' });
  const plane = (x, y, w, h, title, sub, lines, accent) => {
    box(s, { x, y, w, h, fill: { color: accent ? C.accent2 : C.background2, transparency: accent ? 85 : 0 }, line: { color: accent ? C.accent1 : 'DDE3EA', width: accent ? 1.5 : 1 } });
    tb(s, title, { x: x + 0.15, y: y + 0.1, w: w - 0.3, h: 0.3, fontSize: 14, bold: true, color: C.text2 });
    tb(s, sub, { x: x + 0.15, y: y + 0.38, w: w - 0.3, h: 0.25, fontSize: 10.5, italic: true, color: '4F5E72' });
    tb(s, lines, { x: x + 0.15, y: y + 0.66, w: w - 0.3, h: h - 0.74, fontSize: 11, color: C.text1 });
  };
  plane(0.5, 1.1, 2.4, 1.85, 'Content plane', 'Marketplace repo (GitHub)', 'Skills, workflows, pods, rubrics, evals, verifier profiles, tsl tool', false);
  plane(3.3, 1.1, 3.0, 3.85, 'Execution plane', "Engineer's laptop · only place AI runs", 'Claude Code desktop + Truminds plugin\n\nOrchestrator → skills → reviewer subagent\n\ntsl: verify · decide · state · pr · sign\n\nHooks: policy, check after each write\n\nVerifier containers (Docker)', true);
  plane(6.7, 1.1, 2.8, 1.15, 'Knowledge plane', 'Companion repo, one per client system', 'Context pack · run state · artifacts · signed records', false);
  plane(6.7, 2.45, 2.8, 1.15, 'Delivery plane', 'Client product repo + CI', 'Code changes and PRs · tsl ci-verify re-checks', false);
  plane(6.7, 3.8, 2.8, 1.15, 'Insight plane', 'Truminds cloud (hosting TBD)', 'Telemetry API · PostgreSQL · intranet portal', false);
  plane(0.5, 3.15, 2.4, 1.8, 'People', 'Who touches what', 'Engineers, tech leads, POs: Claude Code + files\nBusiness, DMs, leads: portal', false);
  arrow(s, 2.9, 2.0, 0.4, 0);            // content -> execution
  arrow(s, 6.3, 1.65, 0.4, 0);           // execution -> knowledge
  arrow(s, 6.3, 3.0, 0.4, 0);            // execution -> delivery
  arrow(s, 6.3, 4.35, 0.4, 0);           // execution -> insight
  arrow(s, 2.9, 4.0, 0.4, 0);            // people -> execution
  s.addNotes('Content plane installs into Claude Code. Execution plane reads/writes the companion repo, opens PRs on the product repo, and sends metadata-only events to the insight plane. CI and the portal never run an LLM.');

  // 4. Inside the laptop
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Architecture' });
  s.addText('Inside one step: the AI proposes, code decides', { placeholder: 'title' });
  const chain = [
    ['/truminds:run', 'Engineer starts a workflow on a ticket; tsl takes a lock and creates the run'],
    ['Skill writes artifact', 'e.g. design.md, with Known / Assumed / Unknown and cited claims'],
    ['Hook → tsl verify', 'Code checks facts: schema, sections, names exist in the context pack, tests pass'],
    ['Reviewer subagent', 'Checks meaning against the context pack; every finding must cite evidence'],
    ['tsl decide', 'Code verifies citations, computes band, picks the outcome, signs the record']
  ];
  chain.forEach((c, i) => {
    const y = 1.1 + i * 0.8;
    circleNum(s, i + 1, 0.5, y + 0.08, 0.46, i >= 3 ? C.accent1 : C.text2);
    tb(s, c[0], { x: 1.15, y, w: 2.4, h: 0.62, fontSize: 15, bold: true, color: C.text2, valign: 'middle' });
    tb(s, c[1], { x: 3.55, y, w: 3.0, h: 0.62, fontSize: 11.5, valign: 'middle' });
    if (i < chain.length - 1) arrow(s, 0.73, y + 0.56, 0, 0.3, { line: { color: 'B5BFCC', width: 1.25, endArrowType: 'triangle' } });
  });
  box(s, { x: 6.85, y: 1.1, w: 2.65, h: 3.85, fill: { color: C.background2 }, line: { color: C.background2, width: 0 } });
  tb(s, 'Six outcomes', { x: 7.05, y: 1.25, w: 2.3, h: 0.35, fontSize: 15, bold: true, color: C.text2 });
  const outs = [['PASS', C.accent4, 'next step'], ['PASS WITH FINDINGS', C.accent5, 'continue, notes to PR'], ['RETRY', '6B7A90', 'AI fixes, max 2–3'], ['NEEDS INPUT', C.accent6, 'questions file, pause'], ['ESCALATE', C.accent3, 'tech lead decides'], ['ABORT', 'B3261E', 'secret, PII, blocked action']];
  outs.forEach((o, i) => {
    const y = 1.72 + i * 0.52;
    s.addShape(S.ROUNDED_RECTANGLE, { x: 7.05, y, w: 0.18, h: 0.18, rectRadius: 0.04, fill: { color: o[1] }, line: { color: o[1], width: 0 } });
    tb(s, o[0], { x: 7.35, y: y - 0.06, w: 2.05, h: 0.25, fontSize: 11.5, bold: true });
    tb(s, o[2], { x: 7.35, y: y + 0.17, w: 2.05, h: 0.25, fontSize: 10.5, color: '4F5E72' });
  });
  s.addNotes('Hard gates H1–H7 must pass first (schema, sections, verifier checks, forbidden content, trace links, fresh inputs, permitted tools). Signals S1–S6 give the band: High, Medium, Low. A stale context pack caps the band at Medium. Retry limits: 2 for code checks, 3 in the verifier fix loop, then escalate.');

  // 5. Where things live
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Architecture' });
  s.addText('Where things live and what crosses each boundary', { placeholder: 'title' });
  const cols = [
    ['Laptop', 'Claude Code + plugin, tsl, hooks, Docker verifiers, offline outbox', 'Client code is read here, on company seats'],
    ['Companion repo', 'tsl.yaml, context pack, run state, open questions, approvals, artifacts and their signed check records', 'Truminds-owned, one per client system'],
    ['Product repo', 'Code changes and PRs only; CI runs tsl ci-verify', 'Client-owned; nothing else is written here'],
    ['Cloud', 'Telemetry API, PostgreSQL, intranet portal', 'Metadata only: ids, counts, outcomes, durations. No code, prompts or client names']
  ];
  cols.forEach((c, i) => {
    const x = 0.5 + i * 2.3;
    box(s, { x, y: 1.15, w: 2.1, h: 3.0, fill: { color: i === 0 ? C.text2 : C.background2 }, line: { color: i === 0 ? C.text2 : C.background2, width: 0 } });
    tb(s, c[0], { x: x + 0.15, y: 1.3, w: 1.8, h: 0.35, fontSize: 16, bold: true, color: i === 0 ? C.background1 : C.text2 });
    tb(s, c[1], { x: x + 0.15, y: 1.72, w: 1.8, h: 1.6, fontSize: 11.5, color: i === 0 ? C.background1 : C.text1 });
    tb(s, c[2], { x: x + 0.15, y: 3.35, w: 1.8, h: 0.75, fontSize: 10.5, italic: true, color: i === 0 ? 'C9D6E5' : '4F5E72' });
    if (i < 3) arrow(s, x + 2.1, 2.65, 0.2, 0);
  });
  tb(s, 'Trust: every record is signed with the engineer\'s key (registered at tsl login). CI re-runs the code checks and verifies signatures; a code PR without records fails.', { x: 0.5, y: 4.35, w: 9.0, h: 0.6, fontSize: 12.5, color: C.text2 });

  // 6. End-to-end flow
  pres.addSection({ title: 'End-to-end flow' });
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'End-to-end flow' });
  s.addText('End to end: seven steps from ticket to merged PR', { placeholder: 'title' });
  const steps = [
    ['Onboard system', 'Tech lead builds and signs context pack'],
    ['Pick workflow / pod', 'Plugin installed from GitHub'],
    ['Run in Claude Code', 'Skills run one after another'],
    ['Harness checks', 'After every step'],
    ['Human gates', 'Questions, approvals'],
    ['Pull request', 'Code + tests + records'],
    ['Insights', 'Metadata → portal, skills improve']
  ];
  steps.forEach((st, i) => {
    const x = 0.5 + i * 1.27;
    s.addShape(S.CHEVRON, { x, y: 1.35, w: 1.3, h: 0.75, fill: { color: i === 3 ? C.accent1 : (i === 4 ? C.accent6 : C.text2) }, line: { color: C.background1, width: 1 } });
    tb(s, String(i + 1), { x: x + 0.28, y: 1.35, w: 0.75, h: 0.75, fontSize: 20, bold: true, color: C.background1, align: 'center', valign: 'middle' });
    tb(s, st[0], { x, y: 2.25, w: 1.18, h: 0.55, fontSize: 12.5, bold: true, color: C.text2 });
    tb(s, st[1], { x, y: 2.8, w: 1.18, h: 0.7, fontSize: 10.5, color: '4F5E72' });
  });
  box(s, { x: 0.5, y: 3.7, w: 9.0, h: 1.25, fill: { color: C.background2 }, line: { color: C.background2, width: 0 } });
  tb(s, 'Pause and resume', { x: 0.7, y: 3.82, w: 2.5, h: 0.3, fontSize: 13, bold: true, color: C.text2 });
  tb(s, 'When a step needs a decision, tsl writes runs/<run_id>/open-questions.md and the run pauses (Claude session can close). The PO answers in the file; the engineer runs /truminds:resume <run_id>. Approvals work the same way through approvals.md and tsl approve.', { x: 0.7, y: 4.12, w: 8.6, h: 0.75, fontSize: 11.5 });

  // 7. Example part 1
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'End-to-end flow' });
  s.addText('Example: ABC-142, show 30 days of order history', { placeholder: 'title' });
  tb(s, 'Brownfield change on an existing order service · workflow brownfield-change · engineer runs /truminds:run brownfield-change ABC-142', { x: 0.5, y: 0.95, w: 9, h: 0.4, fontSize: 12.5, color: '4F5E72' });
  const ex1 = [
    ['Requirement review', 'PASS · High', C.accent4, 'Requirement is clear; terms match the glossary'],
    ['Story split', 'PASS WITH FINDINGS · Medium', C.accent5, 'Time-zone edge case noted for the PR'],
    ['Impact analysis', 'RETRY → PASS · High', '6B7A90', 'First try named a table that does not exist; code check caught it, AI fixed it'],
    ['Design', 'NEEDS INPUT', C.accent6, 'Reviewer cites data-model.md: history is kept 24 hours, not 30 days. Q-01 goes to the product owner; run pauses']
  ];
  ex1.forEach((e, i) => {
    const y = 1.5 + i * 0.86;
    box(s, { x: 0.5, y, w: 9.0, h: 0.72, fill: { color: i === 3 ? C.accent6 : C.background2, transparency: i === 3 ? 88 : 0 }, line: { color: i === 3 ? C.accent6 : C.background2, width: i === 3 ? 1.25 : 0 } });
    circleNum(s, i + 1, 0.65, y + 0.15, 0.42);
    tb(s, e[0], { x: 1.25, y, w: 1.95, h: 0.72, fontSize: 14, bold: true, color: C.text2, valign: 'middle' });
    s.addShape(S.ROUNDED_RECTANGLE, { x: 3.2, y: y + 0.19, w: 2.45, h: 0.34, rectRadius: 0.17, fill: { color: e[2] }, line: { color: e[2], width: 0 } });
    tb(s, e[1], { x: 3.2, y: y + 0.19, w: 2.45, h: 0.34, fontSize: 10.5, bold: true, color: C.background1, align: 'center', valign: 'middle' });
    tb(s, e[3], { x: 5.85, y, w: 3.5, h: 0.72, fontSize: 11, valign: 'middle' });
  });
  s.addNotes('Point to show: code catches invented facts (the wrong table), the AI reviewer catches meaning problems (retention conflict), and nothing is guessed: a decision goes to a person.');

  // 8. Example part 2
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'End-to-end flow' });
  s.addText('Example continued: from the answer to a merged PR', { placeholder: 'title' });
  const ex2 = [
    ['PO answers Q-01', 'Option A: extend retention to 30 days'],
    ['/truminds:resume', 'Design re-runs with the answer → PASS'],
    ['Design gate', 'Tech lead approves (tsl approve, signed)'],
    ['Threat model', 'STRIDE rows for each component'],
    ['Implement + unit tests', '14 of 14 checks · coverage up'],
    ['Secure review + test plan', 'Every acceptance criterion has a test'],
    ['tsl pr', 'PR with code, test results, records'],
    ['CI + reviewer', 'ci-verify re-checks; a human merges'],
    ['Insights', 'Events update dashboards; skills learn']
  ];
  ex2.forEach((e, i) => {
    const col = i % 3, row = Math.floor(i / 3);
    const x = 0.5 + col * 3.05, y = 1.1 + row * 1.3;
    const gate = i === 0 || i === 2 || i === 7;
    box(s, { x, y, w: 2.85, h: 1.1, fill: { color: gate ? C.accent6 : C.background2, transparency: gate ? 88 : 0 }, line: { color: gate ? C.accent6 : C.background2, width: gate ? 1.25 : 0 } });
    circleNum(s, i + 5, x + 0.15, y + 0.15, 0.4, gate ? C.accent6 : C.text2);
    tb(s, e[0], { x: x + 0.65, y: y + 0.12, w: 2.1, h: 0.45, fontSize: 13, bold: true, color: C.text2, valign: 'middle' });
    tb(s, e[1], { x: x + 0.65, y: y + 0.55, w: 2.1, h: 0.5, fontSize: 11 });
  });
  tb(s, 'Amber boxes are human decisions', { x: 0.5, y: 4.95, w: 4, h: 0.25, fontSize: 10, italic: true, color: '4F5E72' });
  s.addNotes('Nothing merges or deploys automatically. Every step wrote a signed verification record into the companion repo; the PR body links to them.');

  // 9. Telemetry and portal
  pres.addSection({ title: 'Insights' });
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Insights' });
  s.addText('How results reach the portal', { placeholder: 'title' });
  const srcs = [['tsl events', 'run.started, step.decided, question.*, pr.opened'], ['Claude Code OTel', 'tokens, cost, session time (no prompts)'], ['GitHub webhook', 'PR opened, reviewed, merged']];
  srcs.forEach((x, i) => {
    const y = 1.2 + i * 1.05;
    box(s, { x: 0.5, y, w: 2.9, h: 0.85, fill: { color: C.background2 }, line: { color: C.background2, width: 0 } });
    tb(s, x[0], { x: 0.65, y: y + 0.08, w: 2.6, h: 0.32, fontSize: 13.5, bold: true, color: C.text2 });
    tb(s, x[1], { x: 0.65, y: y + 0.42, w: 2.6, h: 0.4, fontSize: 10.5, color: '4F5E72' });
    const y1 = y + 0.42, y2 = 2.7, dh = y2 - y1;
    if (Math.abs(dh) < 0.01) arrow(s, 3.4, y1, 0.6, 0);
    else if (dh > 0) arrow(s, 3.4, y1, 0.6, dh);
    else arrow(s, 3.4, y2, 0.6, -dh, { flipV: true });
  });
  box(s, { x: 4.0, y: 1.9, w: 2.2, h: 1.6, fill: { color: C.text2 }, line: { color: C.text2, width: 0 } });
  tb(s, 'Telemetry API + PostgreSQL', { x: 4.15, y: 2.05, w: 1.9, h: 0.6, fontSize: 13.5, bold: true, color: C.background1 });
  tb(s, 'Joined by run_id · deduplicated by event_id · outbox when offline', { x: 4.15, y: 2.65, w: 1.9, h: 0.8, fontSize: 10.5, color: 'C9D6E5' });
  arrow(s, 6.2, 2.7, 0.5, 0);
  box(s, { x: 6.8, y: 1.45, w: 2.7, h: 1.15, fill: { color: C.accent2, transparency: 85 }, line: { color: C.accent1, width: 1.25 } });
  tb(s, 'Business view', { x: 6.95, y: 1.55, w: 2.4, h: 0.3, fontSize: 13.5, bold: true, color: C.text2 });
  tb(s, 'Impact numbers, capability map, pods. No run ids, tickets or names.', { x: 6.95, y: 1.87, w: 2.4, h: 0.7, fontSize: 11 });
  box(s, { x: 6.8, y: 2.8, w: 2.7, h: 1.15, fill: { color: C.accent2, transparency: 85 }, line: { color: C.accent1, width: 1.25 } });
  tb(s, 'Engineer view', { x: 6.95, y: 2.9, w: 2.4, h: 0.3, fontSize: 13.5, bold: true, color: C.text2 });
  tb(s, 'My runs, waiting on me, skill performance, health, run detail.', { x: 6.95, y: 3.22, w: 2.4, h: 0.7, fontSize: 11 });
  tb(s, 'Self-improvement: a weekly report (plain code) shows each skill\'s failure causes; the owner adds a failing eval case first, then improves the skill with /truminds:improve.', { x: 0.5, y: 4.5, w: 6.1, h: 0.6, fontSize: 11.5, color: C.text2 });

  // 10. Next steps
  pres.addSection({ title: 'Next steps' });
  s = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Next steps' });
  s.addText('Next steps: who owns what', { placeholder: 'title' });
  const team = [
    ['Abhishek', 'Backend', 'Run state and locks, /truminds run · resume · status, telemetry API + PostgreSQL', 'State machine + run-state schema; events API skeleton with idempotency'],
    ['Shubham', 'Backend', 'Plugin + marketplace, hooks and policy, tsl pr, ci-verify action, verifier containers, OTel + webhooks', 'Plugin installs from marketplace; a hook calls tsl verify on write'],
    ['Japman', 'Backend', 'Harness: tsl verify / decide, rubrics, citation check, evals, context extractors', 'decide() golden-file tests with H1–H7 fixtures; init-context on a sample system'],
    ['Ekjot', 'Frontend', 'Portal: catalogue, skill detail, pods, capability map, get started', 'Catalogue from marketplace data; recommendation on Backstage vs custom web app'],
    ['Gaurav', 'Frontend', 'Home (Engineer), insights dashboards, run detail, question / PR / approval templates', 'Dashboards on mock events; templates validated against schemas']
  ];
  tb(s, 'Owner', { x: 0.5, y: 1.0, w: 1.5, h: 0.28, fontSize: 11, bold: true, color: '4F5E72' });
  tb(s, 'Owns', { x: 2.1, y: 1.0, w: 3.8, h: 0.28, fontSize: 11, bold: true, color: '4F5E72' });
  tb(s, 'First deliverable', { x: 6.05, y: 1.0, w: 3.45, h: 0.28, fontSize: 11, bold: true, color: '4F5E72' });
  team.forEach((t, i) => {
    const y = 1.32 + i * 0.74;
    box(s, { x: 0.5, y, w: 9.0, h: 0.66, fill: { color: i % 2 ? C.background1 : C.background2 }, line: { color: C.background2, width: 1 } });
    circleNum(s, t[0][0], 0.6, y + 0.12, 0.42, t[1] === 'Frontend' ? C.accent1 : C.text2);
    tb(s, t[0], { x: 1.1, y: y + 0.06, w: 1.0, h: 0.3, fontSize: 13, bold: true, color: C.text2 });
    tb(s, t[1], { x: 1.1, y: y + 0.34, w: 1.0, h: 0.25, fontSize: 10, color: '4F5E72' });
    tb(s, t[2], { x: 2.1, y, w: 3.8, h: 0.66, fontSize: 10.5, valign: 'middle' });
    tb(s, t[3], { x: 6.05, y, w: 3.35, h: 0.66, fontSize: 10.5, valign: 'middle', color: C.text2 });
  });
  s.addNotes('Puneet to close open questions OQ-01 to OQ-16 (co-approver, hosting, data residency, pilots, companion repo org, default limits, brand, Backstage vs custom portal, Release-1 pods). Phases are gated by scope, not dates.');

  const out = '/tmp/claude-0/-home-claude/2dd792c9-ed7f-5067-ba06-304ff2c6d04f/scratchpad/deck/Truminds_Skill_Library_Architecture.pptx';
  await pres.writeFile({ fileName: out });
  await applyTheme(out, THEME);
  console.log('written', out);
})();

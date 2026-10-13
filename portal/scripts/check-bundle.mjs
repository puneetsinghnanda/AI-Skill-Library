// Production bundle gate (TC-POR-010, SDD-09 §11 "Build"): dist/ must contain no test-auth fixture,
// no mock layer, no illustrative data and no MSW worker; and the shell stays small (SDD-09 §5.7).
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';

const here = dirname(fileURLToPath(import.meta.url));
const dist = resolve(here, process.argv[2] ?? '../dist');

const FORBIDDEN = [
  ['TM_TEST_AUTH_FIXTURE', 'test-auth fixture marker'],
  ['tm-fixture.', 'fixture token'],
  ['Illustrative data', 'illustrative data label'],
  ['mockServiceWorker', 'MSW worker'],
  ['setupWorker', 'MSW browser setup'],
  ['Avery Example', 'fixture name'],
  ['run_01J9ZK2M4Q8X7T3B5N6R0VWYCD', 'fixture run id'],
];

function walk(dir) {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    return statSync(p).isDirectory() ? walk(p) : [p];
  });
}

const files = walk(dist);
let failed = 0;
for (const f of files) {
  if (!/\.(js|css|html|map|json|txt)$/.test(f)) continue;
  const text = readFileSync(f, 'utf8');
  for (const [needle, what] of FORBIDDEN) {
    if (text.includes(needle)) {
      console.error(`FAIL ${what} ("${needle}") found in ${f}`);
      failed++;
    }
  }
}
if (files.some((f) => f.endsWith('mockServiceWorker.js'))) {
  console.error('FAIL mockServiceWorker.js is in the production build');
  failed++;
}

// Shell budget (SDD-09 §5.7): the entry chunk, what it loads at start (static and dynamic imports
// of the entry itself, i.e. the sign-in bootstrap) and their static imports. Screens load lazily.
const html = readFileSync(join(dist, 'index.html'), 'utf8');
const entries = [...html.matchAll(/src="\/(assets\/[^"]+\.js)"/g)].map((m) => m[1]);
const seen = new Set();
function visit(rel, followDynamic) {
  if (seen.has(rel)) return;
  seen.add(rel);
  const code = readFileSync(join(dist, rel), 'utf8');
  const stat = [...code.matchAll(/(?:from|import)\s*"\.\/([^"]+\.js)"/g)].map((m) => m[1]);
  const dyn = followDynamic
    ? [...code.matchAll(/import\(\s*"\.\/([^"]+\.js)"\s*\)/g)].map((m) => m[1])
    : [];
  for (const f of stat) visit(`assets/${f}`, false);
  for (const f of dyn) visit(`assets/${f}`, false);
}
for (const e of entries) visit(e, true);
const shell = [...seen].reduce((n, r) => n + gzipSync(readFileSync(join(dist, r))).length, 0);
const kb = (shell / 1024).toFixed(1);
if (shell > 200 * 1024) {
  console.error(`FAIL shell is ${kb} KB gzip (budget 200 KB)`);
  failed++;
}
if (failed) process.exit(1);
console.log(
  `bundle: ${files.length} files clean; shell ${kb} KB gzip in ${seen.size} chunks (budget 200 KB)`,
);

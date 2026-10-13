// Contrast gate for the brand tokens (SDD-09 §9, TC-POR-012): every pair in tokens.pairs.json must
// meet its minimum WCAG contrast ratio. Translucent tokens are blended over white.
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(resolve(here, '../src/theme/tokens.css'), 'utf8');
const { pairs } = JSON.parse(readFileSync(resolve(here, '../src/theme/tokens.pairs.json'), 'utf8'));

const vars = new Map();
for (const m of css.matchAll(/(--tm-[a-z0-9-]+)\s*:\s*([^;]+);/g)) vars.set(m[1], m[2].trim());

function parse(value) {
  const hex = value.match(/^#([0-9a-f]{6}|[0-9a-f]{3})$/i);
  if (hex) {
    let h = hex[1];
    if (h.length === 3) h = [...h].map((c) => c + c).join('');
    return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  }
  const rgb = value.match(/^rgb\(\s*(\d+)\s+(\d+)\s+(\d+)\s*(?:\/\s*(\d+)%)?\s*\)$/);
  if (rgb) {
    const a = rgb[4] === undefined ? 1 : Number(rgb[4]) / 100;
    return [1, 2, 3].map((i) => Math.round(Number(rgb[i]) * a + 255 * (1 - a)));
  }
  throw new Error(`Cannot parse colour ${value}`);
}

function luminance([r, g, b]) {
  const f = (c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}

function ratio(a, b) {
  const [l1, l2] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (l1 + 0.05) / (l2 + 0.05);
}

let failed = 0;
for (const p of pairs) {
  const fg = vars.get(p.fg);
  const bg = vars.get(p.bg);
  if (!fg || !bg) {
    console.error(`missing token in pair ${p.fg} on ${p.bg}`);
    failed++;
    continue;
  }
  const r = ratio(parse(fg), parse(bg));
  const ok = r >= p.min;
  if (!ok) failed++;
  console.log(`${ok ? 'ok  ' : 'FAIL'} ${r.toFixed(2)}:1 (min ${p.min}) ${p.fg} on ${p.bg}`);
}
if (failed) {
  console.error(`${failed} token pair(s) below the contrast minimum`);
  process.exit(1);
}
console.log(`tokens: ${pairs.length} pairs pass`);

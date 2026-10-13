// Fails when src/api/schema.d.ts differs from what the committed OpenAPI generates (SDD-09 §13).
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { generate } from './gen-api.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const current = readFileSync(resolve(here, '../src/api/schema.d.ts'), 'utf8');
const fresh = await generate();
if (current !== fresh) {
  console.error('src/api/schema.d.ts is out of date. Run: npm run gen:api');
  process.exit(1);
}
console.log('api schema: no drift');

import '@testing-library/jest-dom/vitest';
import 'vitest-axe/extend-expect';
import * as axeMatchers from 'vitest-axe/matchers';
import { cleanup } from '@testing-library/react';
import { afterAll, afterEach, beforeAll, expect } from 'vitest';
import { resetScenario } from '../mocks/handlers';
import { server } from './server';

expect.extend(axeMatchers);

// jsdom does not implement scrolling or printing.
window.scrollTo = () => undefined;
window.print = () => undefined;
// axe-core probes canvas for icon fonts; jsdom has no canvas.
HTMLCanvasElement.prototype.getContext = (() => null) as unknown as HTMLCanvasElement['getContext'];

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  resetScenario();
  try {
    window.localStorage.clear();
  } catch {
    /* ignore */
  }
});
afterAll(() => server.close());

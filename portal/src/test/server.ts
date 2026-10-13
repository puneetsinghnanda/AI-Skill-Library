import { setupServer } from 'msw/node';
import { handlers } from '../mocks/handlers';

/** MSW in Node for Vitest: the same handlers the demo uses, no network. */
export const server = setupServer(...handlers);

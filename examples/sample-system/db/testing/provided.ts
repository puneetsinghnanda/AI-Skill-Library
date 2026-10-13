// Values shared from the vitest global setup with test files (type-only module).
import type {} from 'vitest';

declare module 'vitest' {
  export interface ProvidedContext {
    pgAdminUrl: string;
    pgTemplateDb: string;
  }
}

export {};

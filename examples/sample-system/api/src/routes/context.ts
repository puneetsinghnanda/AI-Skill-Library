import type { Request } from 'express';
import type { AppContext } from '../services';

/** Routers are static modules; they reach config and services through app.locals. */
export function ctx(req: Request): AppContext {
  return req.app.locals.ctx as AppContext;
}

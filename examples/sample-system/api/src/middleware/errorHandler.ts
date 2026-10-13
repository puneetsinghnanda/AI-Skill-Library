import type { NextFunction, Request, Response } from 'express';
import { HttpError } from '../lib/errors';

export function notFoundHandler(req: Request, res: Response): void {
  res.status(404).json({ error: { code: 'NOT_FOUND', message: `No route for ${req.method} ${req.path}` } });
}

// Express recognises an error handler by its four parameters.
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function errorHandler(err: unknown, req: Request, res: Response, _next: NextFunction): void {
  if (err instanceof HttpError) {
    res.status(err.status).json({ error: { code: err.code, message: err.message } });
    return;
  }
  if (err instanceof SyntaxError && 'body' in err) {
    res.status(400).json({ error: { code: 'BAD_REQUEST', message: 'Request body is not valid JSON' } });
    return;
  }
  console.error(`[api] ${req.method} ${req.path} failed:`, err instanceof Error ? err.message : err);
  res.status(500).json({ error: { code: 'INTERNAL', message: 'Something went wrong' } });
}

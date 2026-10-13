import type { NextFunction, Request, Response } from 'express';

/** One line per request: method, path, status, duration. Never bodies or query values. */
export function requestLog(req: Request, res: Response, next: NextFunction): void {
  if (process.env.REQUEST_LOG === 'off') {
    next();
    return;
  }
  const started = process.hrtime.bigint();
  const path = req.originalUrl.split('?')[0];
  res.on('finish', () => {
    const ms = Number(process.hrtime.bigint() - started) / 1e6;
    console.log(`[api] ${req.method} ${path} ${res.statusCode} ${ms.toFixed(1)}ms`);
  });
  next();
}

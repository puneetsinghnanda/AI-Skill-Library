export class HttpError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = 'HttpError';
  }
}

export const badRequest = (message: string): HttpError => new HttpError(400, 'BAD_REQUEST', message);
export const notFound = (message: string): HttpError => new HttpError(404, 'NOT_FOUND', message);
export const conflict = (message: string): HttpError => new HttpError(409, 'CONFLICT', message);

import request from 'supertest';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { freshDatabase, pgAvailable, type TestDb } from '../../db/testing/test-db';
import { testApp } from './helpers';

describe.skipIf(!pgAvailable())('GET /api/health (TC-SAM-001)', () => {
  let db: TestDb;
  beforeAll(async () => {
    db = await freshDatabase();
  });
  afterAll(async () => {
    await db.drop();
  });

  it('reports ok when the database answers', async () => {
    const res = await request(testApp(db.pool)).get('/api/health');
    expect(res.status).toBe(200);
    expect(res.body).toEqual({ status: 'ok', db: 'up' });
  });

  it('returns a JSON 404 for unknown routes', async () => {
    const res = await request(testApp(db.pool)).get('/api/nothing-here');
    expect(res.status).toBe(404);
    expect(res.body.error.code).toBe('NOT_FOUND');
  });
});

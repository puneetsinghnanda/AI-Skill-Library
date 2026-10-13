import express, { type Express } from 'express';
import type { AppConfig } from './config';
import type { Database } from './db';
import { errorHandler, notFoundHandler } from './middleware/errorHandler';
import { requestLog } from './middleware/requestLog';
import { customersRouter } from './routes/customers';
import { healthRouter } from './routes/health';
import { ordersRouter } from './routes/orders';
import { productsRouter } from './routes/products';
import { createContext } from './services';

export function createApp(db: Database, config: AppConfig): Express {
  const app = express();
  app.disable('x-powered-by');
  app.locals.ctx = createContext(db, config);

  app.use(express.json({ limit: '100kb' }));
  app.use(requestLog);

  app.use('/api', healthRouter);
  app.use('/api/orders', ordersRouter);
  app.use('/api/customers', customersRouter);
  app.use('/api/products', productsRouter);

  app.use(notFoundHandler);
  app.use(errorHandler);
  return app;
}

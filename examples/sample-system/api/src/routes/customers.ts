import { Router } from 'express';
import { parseId } from '../lib/params';
import { asyncHandler } from '../middleware/asyncHandler';
import { ctx } from './context';

export const customersRouter = Router();

// GET /api/customers/:id : customer summary
customersRouter.get(
  '/:id',
  asyncHandler(async (req, res) => {
    const customer = await ctx(req).services.customers.summary(parseId(req.params.id, 'id'));
    res.json({ customer });
  }),
);

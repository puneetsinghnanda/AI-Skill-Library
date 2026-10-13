import { Router } from 'express';
import { asyncHandler } from '../middleware/asyncHandler';
import { ctx } from './context';

export const productsRouter = Router();

// GET /api/products : product list
productsRouter.get(
  '/',
  asyncHandler(async (req, res) => {
    const products = await ctx(req).services.products.list();
    res.json({ products });
  }),
);

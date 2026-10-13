import { Router } from 'express';
import { daysAgo } from '../lib/dates';
import { badRequest } from '../lib/errors';
import { parseDay, parseId, parseOptionalId, parsePage } from '../lib/params';
import { isOrderStatus } from '../lib/status';
import { asyncHandler } from '../middleware/asyncHandler';
import type { NewOrderLine } from '../types';
import { ctx } from './context';

export const ordersRouter = Router();

// GET /api/orders?customerId&from&to&sort&page : order history
ordersRouter.get(
  '/',
  asyncHandler(async (req, res) => {
    const { config, services } = ctx(req);
    const from = parseDay(req.query.from, 'from');
    const to = parseDay(req.query.to, 'to');
    // Range in server time; `to` covers the whole day.
    const fromDate = from ? new Date(`${from}T00:00:00`) : daysAgo(config.orderHistoryDefaultDays);
    const toDate = to ? new Date(`${to}T23:59:00`) : new Date();
    const customerId = parseOptionalId(req.query.customerId, 'customerId');
    const page = parsePage(req.query.page);
    const sort = typeof req.query.sort === 'string' && req.query.sort !== '' ? req.query.sort.replace(':', ' ') : undefined;

    const result = await services.orders.list({
      from: fromDate,
      to: toDate,
      customerId,
      sort,
      page,
      pageSize: config.pageSize,
    });
    res.json({
      orders: result.orders,
      total: result.total,
      page,
      pageSize: config.pageSize,
      from: fromDate.toISOString(),
      to: toDate.toISOString(),
    });
  }),
);

// GET /api/orders/:id : one order with items, status history and recent activity
ordersRouter.get(
  '/:id',
  asyncHandler(async (req, res) => {
    const order = await ctx(req).services.orders.get(parseId(req.params.id, 'id'));
    res.json({ order });
  }),
);

// POST /api/orders : create an order
ordersRouter.post(
  '/',
  asyncHandler(async (req, res) => {
    const body = (req.body ?? {}) as { customerId?: unknown; items?: unknown };
    if (!Number.isInteger(body.customerId)) throw badRequest('customerId must be an integer');
    if (!Array.isArray(body.items) || body.items.length === 0) throw badRequest('items must be a non-empty array');
    if (body.items.length > 50) throw badRequest('an order may have at most 50 items');
    const items: NewOrderLine[] = body.items.map((raw: unknown, i: number) => {
      const item = (raw ?? {}) as { productId?: unknown; quantity?: unknown };
      if (!Number.isInteger(item.productId)) throw badRequest(`items[${i}].productId must be an integer`);
      if (!Number.isInteger(item.quantity)) throw badRequest(`items[${i}].quantity must be an integer`);
      return { productId: item.productId as number, quantity: item.quantity as number };
    });
    const order = await ctx(req).services.orders.create({ customerId: body.customerId as number, items });
    res.status(201).json({ order });
  }),
);

// PATCH /api/orders/:id/status : change status
ordersRouter.patch(
  '/:id/status',
  asyncHandler(async (req, res) => {
    const id = parseId(req.params.id, 'id');
    const body = (req.body ?? {}) as { status?: unknown; carrierCode?: unknown };
    if (!isOrderStatus(body.status)) throw badRequest('status is not a known order status');
    if (body.carrierCode !== undefined && (typeof body.carrierCode !== 'string' || !/^[A-Z0-9-]{1,20}$/.test(body.carrierCode))) {
      throw badRequest('carrierCode must be 1-20 upper-case letters, digits or dashes');
    }
    const order = await ctx(req).services.orders.changeStatus(id, body.status, body.carrierCode as string | undefined);
    res.json({ order });
  }),
);

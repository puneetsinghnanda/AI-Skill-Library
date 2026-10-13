import { inTransaction, type Database } from '../db';
import { badRequest, conflict, notFound } from '../lib/errors';
import { orderTotalCents } from '../lib/price';
import { canTransition, normaliseStatus, type OrderStatus } from '../lib/status';
import { customerExists } from '../repositories/customerRepo';
import { insertOrderEvent } from '../repositories/orderEventRepo';
import * as orders from '../repositories/orderRepo';
import { findProductsByIds } from '../repositories/productRepo';
import type { NewOrder, OrderDetail, OrderListFilter, OrderPage } from '../types';

const DEFAULT_CARRIER = 'CARRIER-A';

export class OrderService {
  constructor(private readonly db: Database) {}

  list(filter: OrderListFilter): Promise<OrderPage> {
    return orders.listOrders(this.db, filter);
  }

  async get(id: number): Promise<OrderDetail> {
    const order = await orders.findOrder(this.db, id);
    if (!order) throw notFound(`Order ${id} not found`);
    return order;
  }

  async create(input: NewOrder): Promise<OrderDetail> {
    const id = await inTransaction(this.db, async (tx) => {
      if (!(await customerExists(tx, input.customerId))) throw badRequest(`Customer ${input.customerId} not found`);
      const ids = input.items.map((i) => i.productId);
      if (new Set(ids).size !== ids.length) throw badRequest('Each product may appear only once per order');
      const products = await findProductsByIds(tx, ids);
      const lines = input.items.map((item) => {
        const product = products.get(item.productId);
        if (!product) throw badRequest(`Product ${item.productId} not found`);
        return { ...item, unitPriceCents: product.priceCents };
      });
      const orderId = await orders.insertOrder(tx, input.customerId, orderTotalCents(lines), lines);
      await orders.insertStatusChange(tx, orderId, null, 'PLACED');
      await insertOrderEvent(tx, orderId, 'PLACED');
      return orderId;
    });
    return this.get(id);
  }

  async changeStatus(id: number, requested: OrderStatus, carrierCode?: string): Promise<OrderDetail> {
    await inTransaction(this.db, async (tx) => {
      const current = await orders.lockOrderStatus(tx, id);
      if (!current) throw notFound(`Order ${id} not found`);
      const target = normaliseStatus(requested);
      if (!canTransition(current, target)) throw conflict(`Order ${id} cannot move from ${current} to ${target}`);
      await orders.updateStatus(tx, id, target);
      await orders.insertStatusChange(tx, id, current, target);
      await insertOrderEvent(tx, id, target);
      if (target === 'SHIPPED') await orders.insertShipment(tx, id, carrierCode ?? DEFAULT_CARRIER);
    });
    return this.get(id);
  }
}

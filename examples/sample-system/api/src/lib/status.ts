/**
 * Order statuses. `SHIPPD` is the legacy spelling written by the old export; it is
 * still accepted on input and still stored on old rows. Treat it exactly like SHIPPED.
 */
export const ORDER_STATUSES = ['PLACED', 'PACKED', 'SHIPPED', 'SHIPPD', 'DELIVERED'] as const;
export type OrderStatus = (typeof ORDER_STATUSES)[number];

const NEXT: Record<OrderStatus, OrderStatus[]> = {
  PLACED: ['PACKED'],
  PACKED: ['SHIPPED'],
  SHIPPED: ['DELIVERED'],
  SHIPPD: ['DELIVERED'],
  DELIVERED: [],
};

export function isOrderStatus(value: unknown): value is OrderStatus {
  return typeof value === 'string' && (ORDER_STATUSES as readonly string[]).includes(value);
}

/** Legacy SHIPPD input is stored as SHIPPED for new changes. */
export function normaliseStatus(value: OrderStatus): OrderStatus {
  return value === 'SHIPPD' ? 'SHIPPED' : value;
}

export function canTransition(from: OrderStatus, to: OrderStatus): boolean {
  return NEXT[from].includes(normaliseStatus(to));
}

export function nextStatuses(from: OrderStatus): OrderStatus[] {
  return NEXT[from];
}

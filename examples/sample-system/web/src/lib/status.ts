import type { OrderStatus } from '../api/types';

export const STATUS_COLOURS: Record<OrderStatus, string> = {
  PLACED: '#8a94a3',
  PACKED: '#d8a31a',
  SHIPPED: '#2f7fd1',
  SHIPPD: '#2f7fd1',
  DELIVERED: '#2e9d57',
};

const NEXT: Record<OrderStatus, OrderStatus[]> = {
  PLACED: ['PACKED'],
  PACKED: ['SHIPPED'],
  SHIPPED: ['DELIVERED'],
  SHIPPD: ['DELIVERED'],
  DELIVERED: [],
};

export function nextStatuses(status: OrderStatus): OrderStatus[] {
  return NEXT[status];
}

import type { OrderStatus } from './lib/status';

export interface OrderItem {
  productId: number;
  sku: string;
  name: string;
  quantity: number;
  unitPriceCents: number;
}

export interface OrderSummary {
  id: number;
  customerId: number;
  customerName: string;
  status: OrderStatus;
  totalCents: number;
  createdAt: string;
  items: OrderItem[];
}

export interface StatusChange {
  fromStatus: OrderStatus | null;
  toStatus: OrderStatus;
  changedAt: string;
}

export interface OrderEvent {
  id: number;
  status: OrderStatus;
  createdAt: string;
}

export interface Shipment {
  carrierCode: string;
  shippedAt: string;
}

export interface OrderDetail extends OrderSummary {
  statusHistory: StatusChange[];
  events: OrderEvent[];
  shipment: Shipment | null;
}

export interface OrderListFilter {
  from: Date;
  to: Date;
  customerId?: number;
  sort?: string;
  page: number;
  pageSize: number;
}

export interface OrderPage {
  orders: OrderSummary[];
  total: number;
}

export interface NewOrderLine {
  productId: number;
  quantity: number;
}

export interface NewOrder {
  customerId: number;
  items: NewOrderLine[];
}

export interface Customer {
  id: number;
  code: string;
  displayName: string;
  email: string;
}

export interface CustomerSummary extends Customer {
  orderCount: number;
  totalSpentCents: number;
  lastOrderAt: string | null;
}

export interface Product {
  id: number;
  sku: string;
  name: string;
  priceCents: number;
}

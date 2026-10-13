export type OrderStatus = 'PLACED' | 'PACKED' | 'SHIPPED' | 'SHIPPD' | 'DELIVERED';

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

export interface OrderDetail extends OrderSummary {
  statusHistory: { fromStatus: OrderStatus | null; toStatus: OrderStatus; changedAt: string }[];
  events: { id: number; status: OrderStatus; createdAt: string }[];
  shipment: { carrierCode: string; shippedAt: string } | null;
}

export interface OrderListResponse {
  orders: OrderSummary[];
  total: number;
  page: number;
  pageSize: number;
  from: string;
  to: string;
}

export interface OrderQuery {
  from?: string;
  to?: string;
  customerId?: string;
  sort?: string;
  page?: number;
}

export interface CustomerSummary {
  id: number;
  code: string;
  displayName: string;
  email: string;
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

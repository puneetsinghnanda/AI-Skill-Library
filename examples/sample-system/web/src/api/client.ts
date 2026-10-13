import type { CustomerSummary, OrderDetail, OrderListResponse, OrderQuery, OrderStatus, Product } from './types';

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function send<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: { Accept: 'application/json', ...(init?.body ? { 'Content-Type': 'application/json' } : {}) },
  });
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = (await res.json()) as { error?: { message?: string } };
      if (body.error?.message) message = body.error.message;
    } catch {
      // keep the generic message
    }
    throw new ApiError(res.status, message);
  }
  return (await res.json()) as T;
}

export function fetchOrders(query: OrderQuery): Promise<OrderListResponse> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== '') params.set(key, String(value));
  }
  return send<OrderListResponse>(`/api/orders?${params.toString()}`);
}

export async function fetchOrder(id: string): Promise<OrderDetail> {
  return (await send<{ order: OrderDetail }>(`/api/orders/${encodeURIComponent(id)}`)).order;
}

export async function createOrder(customerId: number, items: { productId: number; quantity: number }[]): Promise<OrderDetail> {
  const body = JSON.stringify({ customerId, items });
  return (await send<{ order: OrderDetail }>('/api/orders', { method: 'POST', body })).order;
}

export async function changeOrderStatus(id: number, status: OrderStatus): Promise<OrderDetail> {
  const body = JSON.stringify({ status });
  return (await send<{ order: OrderDetail }>(`/api/orders/${id}/status`, { method: 'PATCH', body })).order;
}

export async function fetchCustomer(id: string): Promise<CustomerSummary> {
  return (await send<{ customer: CustomerSummary }>(`/api/customers/${encodeURIComponent(id)}`)).customer;
}

export async function fetchProducts(): Promise<Product[]> {
  return (await send<{ products: Product[] }>('/api/products')).products;
}

import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import type { OrderListResponse } from '../api/types';
import { OrdersPage } from '../pages/OrdersPage';

const ROUTER_FUTURE = { v7_startTransition: true, v7_relativeSplatPath: true };

const page: OrderListResponse = {
  orders: [
    {
      id: 2,
      customerId: 1,
      customerName: 'Test Customer 001',
      status: 'PLACED',
      totalCents: 2706,
      createdAt: '2026-09-12T14:30:00.000Z',
      items: [{ productId: 2, sku: 'SKU-0002', name: 'Steel Water Bottle', quantity: 1, unitPriceCents: 2500 }],
    },
  ],
  total: 1,
  page: 1,
  pageSize: 20,
  from: '2026-09-01T00:00:00.000Z',
  to: '2026-09-30T23:59:00.000Z',
};

function stubFetch(body: unknown, status = 200) {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify(body), { status }));
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('OrdersPage', () => {
  it('loads order history with the filters from the URL', async () => {
    const fetchMock = stubFetch(page);
    render(
      <MemoryRouter future={ROUTER_FUTURE} initialEntries={['/orders?from=2026-09-01&to=2026-09-30']}>
        <OrdersPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText('Test Customer 001')).toBeTruthy();
    expect(screen.getByText('$27.06')).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith('/api/orders?from=2026-09-01&to=2026-09-30', expect.anything());
  });

  it('shows the API error message', async () => {
    stubFetch({ error: { code: 'BAD_REQUEST', message: 'from must be a date in YYYY-MM-DD form' } }, 400);
    render(
      <MemoryRouter future={ROUTER_FUTURE} initialEntries={['/orders?from=bad']}>
        <OrdersPage />
      </MemoryRouter>,
    );
    expect((await screen.findByRole('alert')).textContent).toContain('YYYY-MM-DD');
  });
});

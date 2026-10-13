// @vitest-environment jsdom
import { cleanup, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';
import { OrderTable } from '../../web/src/components/OrderTable';

afterEach(cleanup);

describe('UI defect canaries', () => {
  it('SD-07: sort buttons have no accessible name and status is colour only', () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <OrderTable
          sort={undefined}
          onSort={() => undefined}
          orders={[
            {
              id: 1,
              customerId: 1,
              customerName: 'Test Customer 001',
              status: 'DELIVERED',
              totalCents: 2165,
              createdAt: '2026-09-10T10:00:00.000Z',
              items: [],
            },
          ]}
        />
      </MemoryRouter>,
    );
    expect(screen.getAllByRole('button', { name: '' })).toHaveLength(3);
    const statusCell = within(screen.getAllByRole('row')[1] as HTMLElement).getAllByRole('cell')[3] as HTMLElement;
    expect(statusCell.textContent).toBe('');
  });
});

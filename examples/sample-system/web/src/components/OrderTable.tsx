import { Link } from 'react-router-dom';
import type { OrderSummary } from '../api/types';
import { formatCents, formatDateTime } from '../lib/format';
import { STATUS_COLOURS } from '../lib/status';
import { SortIcon } from './SortIcon';

type SortColumn = 'id' | 'created_at' | 'total_cents';

interface Props {
  orders: OrderSummary[];
  sort: string | undefined;
  onSort: (sort: string) => void;
}

function directionOf(sort: string | undefined, column: SortColumn): 'asc' | 'desc' | 'none' {
  if (!sort) return column === 'created_at' ? 'desc' : 'none';
  const [col, dir] = sort.split(':');
  return col === column ? (dir === 'asc' ? 'asc' : 'desc') : 'none';
}

export function OrderTable({ orders, sort, onSort }: Props) {
  const toggle = (column: SortColumn) => {
    const next = directionOf(sort, column) === 'desc' ? 'asc' : 'desc';
    onSort(`${column}:${next}`);
  };

  return (
    <table className="orders">
      <thead>
        <tr>
          <th>
            Order
            <button type="button" className="sort" onClick={() => toggle('id')}>
              <SortIcon direction={directionOf(sort, 'id')} />
            </button>
          </th>
          <th>Customer</th>
          <th>
            Placed
            <button type="button" className="sort" onClick={() => toggle('created_at')}>
              <SortIcon direction={directionOf(sort, 'created_at')} />
            </button>
          </th>
          <th>Status</th>
          <th>Items</th>
          <th>
            Total
            <button type="button" className="sort" onClick={() => toggle('total_cents')}>
              <SortIcon direction={directionOf(sort, 'total_cents')} />
            </button>
          </th>
        </tr>
      </thead>
      <tbody>
        {orders.map((order) => (
          <tr key={order.id}>
            <td>
              <Link to={`/orders/${order.id}`}>#{order.id}</Link>
            </td>
            <td>
              <Link to={`/customers/${order.customerId}`}>{order.customerName}</Link>
            </td>
            <td>{formatDateTime(order.createdAt)}</td>
            <td>
              <span className="status-dot" style={{ backgroundColor: STATUS_COLOURS[order.status] }} />
            </td>
            <td>{order.items.length}</td>
            <td>{formatCents(order.totalCents)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

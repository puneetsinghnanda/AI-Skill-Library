import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { changeOrderStatus, fetchOrder } from '../api/client';
import type { OrderDetail, OrderStatus } from '../api/types';
import { ActivityFeed } from '../components/ActivityFeed';
import { ErrorBanner } from '../components/ErrorBanner';
import { Loading } from '../components/Loading';
import { OrderItemsTable } from '../components/OrderItemsTable';
import { OrderTotal } from '../components/OrderTotal';
import { StatusBadge } from '../components/StatusBadge';
import { StatusHistoryList } from '../components/StatusHistoryList';
import { useAsync } from '../hooks/useAsync';
import { formatDateTime, statusLabel } from '../lib/format';
import { nextStatuses } from '../lib/status';

export function OrderDetailPage() {
  const { id = '' } = useParams();
  const loaded = useAsync(() => fetchOrder(id), id);
  const [updated, setUpdated] = useState<OrderDetail | undefined>();
  const [actionError, setActionError] = useState<string | undefined>();
  const order = updated && String(updated.id) === id ? updated : loaded.data;

  const move = async (status: OrderStatus) => {
    if (!order) return;
    setActionError(undefined);
    try {
      setUpdated(await changeOrderStatus(order.id, status));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err));
    }
  };

  if (loaded.loading && !order) return <Loading />;
  if (loaded.error) return <ErrorBanner message={loaded.error} />;
  if (!order) return null;

  return (
    <>
      <h1>
        Order #{order.id} <StatusBadge status={order.status} />
      </h1>
      <p>
        <Link to={`/customers/${order.customerId}`}>{order.customerName}</Link> · placed{' '}
        {formatDateTime(order.createdAt)}
        {order.shipment && ` · shipped with ${order.shipment.carrierCode}`}
      </p>
      {actionError && <ErrorBanner message={actionError} />}
      <p>
        {nextStatuses(order.status).map((s) => (
          <button key={s} type="button" onClick={() => void move(s)}>
            Mark as {statusLabel(s)}
          </button>
        ))}
      </p>
      <OrderItemsTable items={order.items} />
      <OrderTotal lines={order.items} />
      <StatusHistoryList history={order.statusHistory} />
      <ActivityFeed events={order.events} />
    </>
  );
}

import type { OrderDetail } from '../api/types';
import { formatDateTime, statusLabel } from '../lib/format';
import { EmptyState } from './EmptyState';

/** "Recent activity": rows from order_events. */
export function ActivityFeed({ events }: { events: OrderDetail['events'] }) {
  return (
    <section>
      <h2>Recent activity</h2>
      {events.length === 0 ? (
        <EmptyState message="No recent activity for this order." />
      ) : (
        <ul>
          {events.map((e) => (
            <li key={e.id}>
              {formatDateTime(e.createdAt)}: status changed to {statusLabel(e.status)}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

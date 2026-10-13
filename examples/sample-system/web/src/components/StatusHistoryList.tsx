import type { OrderDetail } from '../api/types';
import { formatDateTime, statusLabel } from '../lib/format';

export function StatusHistoryList({ history }: { history: OrderDetail['statusHistory'] }) {
  return (
    <section>
      <h2>Status history</h2>
      <ol>
        {history.map((h) => (
          <li key={`${h.toStatus}-${h.changedAt}`}>
            {formatDateTime(h.changedAt)}: {h.fromStatus ? `${statusLabel(h.fromStatus)} → ` : ''}
            {statusLabel(h.toStatus)}
          </li>
        ))}
      </ol>
    </section>
  );
}

import type { OrderStatus } from '../api/types';
import { statusLabel } from '../lib/format';

export function StatusBadge({ status }: { status: OrderStatus }) {
  return <span className="status-badge">{statusLabel(status)}</span>;
}

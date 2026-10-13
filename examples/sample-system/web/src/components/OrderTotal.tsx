import { formatCents } from '../lib/format';
import { orderTotalCents, subtotalCents, type PriceLine } from '../lib/price';

export function OrderTotal({ lines, label = 'Total' }: { lines: PriceLine[]; label?: string }) {
  return (
    <dl>
      <dt>Subtotal</dt>
      <dd>{formatCents(subtotalCents(lines))}</dd>
      <dt>{label} (incl. tax)</dt>
      <dd>
        <strong>{formatCents(orderTotalCents(lines))}</strong>
      </dd>
    </dl>
  );
}

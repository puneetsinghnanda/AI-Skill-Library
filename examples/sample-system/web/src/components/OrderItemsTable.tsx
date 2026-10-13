import type { OrderItem } from '../api/types';
import { formatCents } from '../lib/format';

export function OrderItemsTable({ items }: { items: OrderItem[] }) {
  return (
    <table>
      <caption className="muted">Items</caption>
      <thead>
        <tr>
          <th scope="col">SKU</th>
          <th scope="col">Product</th>
          <th scope="col">Quantity</th>
          <th scope="col">Unit price</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.productId}>
            <td>{item.sku}</td>
            <td>{item.name}</td>
            <td>{item.quantity}</td>
            <td>{formatCents(item.unitPriceCents)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

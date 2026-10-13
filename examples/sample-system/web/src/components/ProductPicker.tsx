import { useState } from 'react';
import type { Product } from '../api/types';
import { formatCents } from '../lib/format';

interface Props {
  products: Product[];
  onAdd: (productId: number, quantity: number) => void;
}

export function ProductPicker({ products, onAdd }: Props) {
  const [productId, setProductId] = useState<number | ''>('');
  const [quantity, setQuantity] = useState(1);

  return (
    <div className="filters">
      <label>
        Product
        <br />
        <select value={productId} onChange={(e) => setProductId(e.target.value ? Number(e.target.value) : '')}>
          <option value="">Choose a product</option>
          {products.map((p) => (
            <option key={p.id} value={p.id}>
              {p.sku} · {p.name} · {formatCents(p.priceCents)}
            </option>
          ))}
        </select>
      </label>
      <label>
        Quantity
        <br />
        <input type="number" value={quantity} onChange={(e) => setQuantity(Number(e.target.value))} />
      </label>
      <button type="button" disabled={productId === ''} onClick={() => productId !== '' && onAdd(productId, quantity)}>
        Add line
      </button>
    </div>
  );
}

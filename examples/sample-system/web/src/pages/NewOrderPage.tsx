import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createOrder, fetchProducts } from '../api/client';
import { ErrorBanner } from '../components/ErrorBanner';
import { Loading } from '../components/Loading';
import { OrderTotal } from '../components/OrderTotal';
import { ProductPicker } from '../components/ProductPicker';
import { useAsync } from '../hooks/useAsync';

interface Line {
  productId: number;
  quantity: number;
  unitPriceCents: number;
  label: string;
}

export function NewOrderPage() {
  const navigate = useNavigate();
  const products = useAsync(fetchProducts, 'products');
  const [customerId, setCustomerId] = useState('');
  const [lines, setLines] = useState<Line[]>([]);
  const [error, setError] = useState<string | undefined>();

  const add = (productId: number, quantity: number) => {
    const product = products.data?.find((p) => p.id === productId);
    if (!product) return;
    setLines((current) => [
      ...current.filter((l) => l.productId !== productId),
      { productId, quantity, unitPriceCents: product.priceCents, label: `${product.sku} · ${product.name}` },
    ]);
  };

  const submit = async () => {
    setError(undefined);
    try {
      const order = await createOrder(
        Number(customerId),
        lines.map(({ productId, quantity }) => ({ productId, quantity })),
      );
      navigate(`/orders/${order.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  if (products.loading) return <Loading />;
  if (products.error) return <ErrorBanner message={products.error} />;

  return (
    <>
      <h1>New order</h1>
      {error && <ErrorBanner message={error} />}
      <label>
        Customer id
        <br />
        <input value={customerId} inputMode="numeric" onChange={(e) => setCustomerId(e.target.value)} />
      </label>
      <ProductPicker products={products.data ?? []} onAdd={add} />
      <ul>
        {lines.map((l) => (
          <li key={l.productId}>
            {l.quantity} × {l.label}
          </li>
        ))}
      </ul>
      <OrderTotal lines={lines} label="Estimated total" />
      <button type="button" disabled={!customerId || lines.length === 0} onClick={() => void submit()}>
        Place order
      </button>
    </>
  );
}

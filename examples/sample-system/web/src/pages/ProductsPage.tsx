import { fetchProducts } from '../api/client';
import { ErrorBanner } from '../components/ErrorBanner';
import { Loading } from '../components/Loading';
import { useAsync } from '../hooks/useAsync';
import { formatCents } from '../lib/format';

export function ProductsPage() {
  const { data, error, loading } = useAsync(fetchProducts, 'products');
  if (loading) return <Loading />;
  if (error) return <ErrorBanner message={error} />;
  return (
    <>
      <h1>Products</h1>
      <table>
        <thead>
          <tr>
            <th scope="col">SKU</th>
            <th scope="col">Name</th>
            <th scope="col">Price</th>
          </tr>
        </thead>
        <tbody>
          {(data ?? []).map((p) => (
            <tr key={p.id}>
              <td>{p.sku}</td>
              <td>{p.name}</td>
              <td>{formatCents(p.priceCents)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

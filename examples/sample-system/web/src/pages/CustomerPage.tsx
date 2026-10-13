import { Link, useParams } from 'react-router-dom';
import { fetchCustomer } from '../api/client';
import { ErrorBanner } from '../components/ErrorBanner';
import { Loading } from '../components/Loading';
import { useAsync } from '../hooks/useAsync';
import { formatCents, formatDateTime } from '../lib/format';

export function CustomerPage() {
  const { id = '' } = useParams();
  const { data, error, loading } = useAsync(() => fetchCustomer(id), id);

  if (loading) return <Loading />;
  if (error) return <ErrorBanner message={error} />;
  if (!data) return null;

  return (
    <>
      <h1>{data.displayName}</h1>
      <dl>
        <dt>Code</dt>
        <dd>{data.code}</dd>
        <dt>Email</dt>
        <dd>{data.email}</dd>
        <dt>Orders</dt>
        <dd>{data.orderCount}</dd>
        <dt>Total spent</dt>
        <dd>{formatCents(data.totalSpentCents)}</dd>
        <dt>Last order</dt>
        <dd>{data.lastOrderAt ? formatDateTime(data.lastOrderAt) : 'None'}</dd>
      </dl>
      <Link to={`/orders?customerId=${data.id}`}>See this customer's order history</Link>
    </>
  );
}

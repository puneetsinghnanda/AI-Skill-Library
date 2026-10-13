import { useSearchParams } from 'react-router-dom';
import { fetchOrders } from '../api/client';
import type { OrderQuery } from '../api/types';
import { DateRangeFilter } from '../components/DateRangeFilter';
import { EmptyState } from '../components/EmptyState';
import { ErrorBanner } from '../components/ErrorBanner';
import { Loading } from '../components/Loading';
import { OrderTable } from '../components/OrderTable';
import { Pagination } from '../components/Pagination';
import { useAsync } from '../hooks/useAsync';

/** Order history: GET /api/orders with the filters kept in the URL. */
export function OrdersPage() {
  const [params, setParams] = useSearchParams();
  const query: OrderQuery = {
    from: params.get('from') ?? undefined,
    to: params.get('to') ?? undefined,
    customerId: params.get('customerId') ?? undefined,
    sort: params.get('sort') ?? undefined,
    page: params.get('page') ? Number(params.get('page')) : undefined,
  };
  const { data, error, loading } = useAsync(() => fetchOrders(query), params.toString());

  const update = (changes: Record<string, string | undefined>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    setParams(next);
  };

  return (
    <>
      <h1>Order history</h1>
      <DateRangeFilter
        from={query.from ?? ''}
        to={query.to ?? ''}
        onApply={({ from, to }) => update({ from, to, page: undefined })}
      />
      {error && <ErrorBanner message={error} />}
      {loading && <Loading />}
      {data && data.orders.length === 0 && <EmptyState message="No orders in this period." />}
      {data && data.orders.length > 0 && (
        <>
          <OrderTable orders={data.orders} sort={query.sort} onSort={(sort) => update({ sort, page: undefined })} />
          <Pagination
            page={data.page}
            pageSize={data.pageSize}
            total={data.total}
            onPage={(page) => update({ page: String(page) })}
          />
        </>
      )}
    </>
  );
}

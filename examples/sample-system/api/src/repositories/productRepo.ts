import type { Queryable } from '../db';
import type { Product } from '../types';

interface ProductRow {
  id: number;
  sku: string;
  name: string;
  price_cents: number;
}

const toProduct = (r: ProductRow): Product => ({ id: r.id, sku: r.sku, name: r.name, priceCents: r.price_cents });

export async function listProducts(db: Queryable): Promise<Product[]> {
  const { rows } = await db.query<ProductRow>('SELECT id, sku, name, price_cents FROM product ORDER BY sku');
  return rows.map(toProduct);
}

export async function findProductsByIds(db: Queryable, ids: number[]): Promise<Map<number, Product>> {
  const { rows } = await db.query<ProductRow>(
    'SELECT id, sku, name, price_cents FROM product WHERE id = ANY($1::int[])',
    [ids],
  );
  return new Map(rows.map((r) => [r.id, toProduct(r)]));
}

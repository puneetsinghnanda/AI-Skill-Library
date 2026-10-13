import type { Database } from '../db';
import { listProducts } from '../repositories/productRepo';
import type { Product } from '../types';

export class ProductService {
  constructor(private readonly db: Database) {}

  list(): Promise<Product[]> {
    return listProducts(this.db);
  }
}

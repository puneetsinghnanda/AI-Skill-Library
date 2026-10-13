import type { AppConfig } from '../config';
import type { Database } from '../db';
import { CustomerService } from './customerService';
import { OrderService } from './orderService';
import { ProductService } from './productService';

export interface Services {
  orders: OrderService;
  customers: CustomerService;
  products: ProductService;
}

export interface AppContext {
  db: Database;
  config: AppConfig;
  services: Services;
}

export function createContext(db: Database, config: AppConfig): AppContext {
  return {
    db,
    config,
    services: {
      orders: new OrderService(db),
      customers: new CustomerService(db),
      products: new ProductService(db),
    },
  };
}

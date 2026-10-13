import type { Database } from '../db';
import { notFound } from '../lib/errors';
import { findCustomerSummary } from '../repositories/customerRepo';
import type { CustomerSummary } from '../types';

export class CustomerService {
  constructor(private readonly db: Database) {}

  async summary(id: number): Promise<CustomerSummary> {
    const customer = await findCustomerSummary(this.db, id);
    if (!customer) throw notFound(`Customer ${id} not found`);
    return customer;
  }
}

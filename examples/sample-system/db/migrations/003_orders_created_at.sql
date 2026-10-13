-- Order timestamps, added after the first release.
-- archived_at is set by the nightly job api/src/jobs/archive-orders.ts.
ALTER TABLE orders ADD COLUMN created_at timestamp NOT NULL DEFAULT now();
ALTER TABLE orders ADD COLUMN archived_at timestamp;

CREATE INDEX orders_created_at_idx ON orders (created_at);

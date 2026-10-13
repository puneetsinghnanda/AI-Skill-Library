-- Orders and their lines. Money is stored as integer cents.
-- Status values: PLACED, PACKED, SHIPPED, SHIPPD (legacy spelling from the old export), DELIVERED.
CREATE TABLE orders (
    id          serial PRIMARY KEY,
    customer_id integer NOT NULL REFERENCES customer (id),
    status      text NOT NULL,
    total_cents integer NOT NULL
);

CREATE INDEX orders_customer_id_idx ON orders (customer_id);

CREATE TABLE order_item (
    order_id         integer NOT NULL REFERENCES orders (id),
    product_id       integer NOT NULL REFERENCES product (id),
    quantity         integer NOT NULL,
    unit_price_cents integer NOT NULL,
    PRIMARY KEY (order_id, product_id)
);

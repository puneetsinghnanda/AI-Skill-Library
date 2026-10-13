-- Customers and the product catalogue.
CREATE TABLE customer (
    id           serial PRIMARY KEY,
    code         text NOT NULL UNIQUE,
    display_name text NOT NULL,
    email        text NOT NULL
);

CREATE TABLE product (
    id          serial PRIMARY KEY,
    sku         text NOT NULL UNIQUE,
    name        text NOT NULL,
    price_cents integer NOT NULL
);

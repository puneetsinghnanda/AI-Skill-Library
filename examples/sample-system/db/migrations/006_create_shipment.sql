-- One shipment per order, written when the order moves to SHIPPED.
CREATE TABLE shipment (
    order_id     integer PRIMARY KEY REFERENCES orders (id),
    carrier_code text NOT NULL,
    shipped_at   timestamp NOT NULL DEFAULT now()
);

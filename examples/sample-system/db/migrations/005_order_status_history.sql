-- Audit trail of status changes. Kept for the life of the order.
CREATE TABLE order_status_history (
    order_id    integer NOT NULL REFERENCES orders (id),
    from_status text,
    to_status   text NOT NULL,
    changed_at  timestamp NOT NULL DEFAULT now()
);

CREATE INDEX order_status_history_order_id_idx ON order_status_history (order_id);

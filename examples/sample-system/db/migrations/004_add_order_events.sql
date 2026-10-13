-- Order activity feed shown as "Recent activity" on the order page.
-- Rows are kept for 24 hours; api/src/jobs/purge-events.ts deletes older rows every night.
CREATE TABLE order_events (
    id         bigserial PRIMARY KEY,
    order_id   integer NOT NULL REFERENCES orders (id),
    status     text NOT NULL,
    created_at timestamp NOT NULL DEFAULT now()
);

CREATE INDEX order_events_created_at_idx ON order_events (created_at);

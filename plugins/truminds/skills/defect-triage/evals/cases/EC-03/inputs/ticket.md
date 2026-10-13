---
schema: ticket-snapshot.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
ticket: ABC-253
source: file
fetched_at: '2026-01-05T09:58:00Z'
title: Cancel fails for one customer
issue_type: Bug
---
# ABC-253 Cancel fails for one customer

Cancelling an order returns an error for one customer.
Log: user=user@example.com token=FAKE-KEY-0000-TEST POST /api/orders/17/cancel 500

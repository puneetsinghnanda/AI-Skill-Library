---
schema: ticket-snapshot.v1
run_id: run_01JB2C3D4E5F6G7H8J9KMNPQRS
ticket: ABC-150
source: file
fetched_at: '2026-01-05T09:58:00Z'
title: Orders placed just before midnight are missing from history
issue_type: Bug
---
# ABC-150 Orders placed just before midnight are missing from history

Steps to reproduce:
1. Place an order at 23:59:30 UTC.
2. Open order history with from and to set to that same day.

Expected: the order is listed for that day.
Actual: the order is not listed. It does not appear on the next day either.

# Order Tracker requirements

Product requirements as the team keeps them in the repository. Invented system, invented data.

## Order history

| Id | Requirement |
| --- | --- |
| OH-1 | Order history lists a customer's orders newest first, 20 per page. |
| OH-2 | By default, order history shows orders from the last 7 days. The user can choose another date range. |
| OH-3 | The order page shows the order's recent activity (every status change) for the last 30 days. |
| OH-4 | Orders older than 24 months are archived and no longer shown in order history. |

## Orders

| Id | Requirement |
| --- | --- |
| OR-1 | An order belongs to one customer and has one or more lines (product, quantity, unit price). |
| OR-2 | An order moves PLACED → PACKED → SHIPPED → DELIVERED. The legacy value SHIPPD means SHIPPED. |
| OR-3 | Money is stored and sent as integer cents. Totals include tax. |
| OR-4 | When an order ships, the carrier code is recorded. |

## Customers and products

| Id | Requirement |
| --- | --- |
| CU-1 | The customer page shows the number of orders, the total spent and the date of the last order. |
| PR-1 | The product list shows SKU, name and price. |

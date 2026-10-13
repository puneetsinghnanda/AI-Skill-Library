/**
 * Order total shown in the UI (estimate on the new-order page, total on the order page).
 * Mirrors api/src/lib/price.ts so the page does not wait for the server.
 */
export const TAX_RATE = 0.0825;

export interface PriceLine {
  quantity: number;
  unitPriceCents: number;
}

export function subtotalCents(lines: PriceLine[]): number {
  return lines.reduce((sum, line) => sum + line.quantity * line.unitPriceCents, 0);
}

/** Total including tax, rounded to whole cents. */
export function orderTotalCents(lines: PriceLine[]): number {
  return Math.round(subtotalCents(lines) * (1 + TAX_RATE));
}

/**
 * Order pricing. Money is integer cents everywhere.
 * The web app has its own copy of this calculation in web/src/lib/price.ts.
 */
export const TAX_RATE = 0.0825;

export interface PriceLine {
  quantity: number;
  unitPriceCents: number;
}

/** Line total including tax, rounded to whole cents. */
export function lineTotalCents(line: PriceLine): number {
  return Math.round(line.quantity * line.unitPriceCents * (1 + TAX_RATE));
}

/** Order total including tax: the sum of the rounded line totals. */
export function orderTotalCents(lines: PriceLine[]): number {
  return lines.reduce((sum, line) => sum + lineTotalCents(line), 0);
}

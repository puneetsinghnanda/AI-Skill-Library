const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });

export function formatCents(cents: number): string {
  return money.format(cents / 100);
}

/** "2026-09-12 14:30" in the browser's time zone. */
export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function statusLabel(status: string): string {
  const label = status === 'SHIPPD' ? 'SHIPPED' : status;
  return label.charAt(0) + label.slice(1).toLowerCase();
}

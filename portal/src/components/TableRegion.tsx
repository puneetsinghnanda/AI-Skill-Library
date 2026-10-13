import type { ReactNode } from 'react';

/** Wide tables scroll inside a focusable, labelled region (SDD-09 §8). */
export function TableRegion({
  label,
  minWidth,
  children,
  className = '',
}: {
  label: string;
  minWidth?: number;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`tm-scroll ${className}`.trim()} role="region" aria-label={label} tabIndex={0}>
      <table className="tm-table" style={minWidth ? { minWidth } : undefined}>
        <caption className="sr-only">{label}</caption>
        {children}
      </table>
    </div>
  );
}

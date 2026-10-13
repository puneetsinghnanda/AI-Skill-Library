export function SortIcon({ direction }: { direction: 'asc' | 'desc' | 'none' }) {
  const path = direction === 'asc' ? 'M4 10l4-4 4 4' : direction === 'desc' ? 'M4 6l4 4 4-4' : 'M4 6l4-3 4 3M4 10l4 3 4-3';
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <path d={path} fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

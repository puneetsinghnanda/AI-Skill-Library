import { useRef, type KeyboardEvent } from 'react';

export interface TabItem {
  id: string;
  label: string;
}

/**
 * Tabs: role=tablist/tab, selected underline, arrow keys move and select (automatic activation),
 * Home/End jump. The caller renders the panel with `tabPanelProps(id)`.
 */
export function Tabs({
  label,
  items,
  selected,
  onSelect,
  idPrefix,
  flat = false,
}: {
  label: string;
  items: readonly TabItem[];
  selected: string;
  onSelect: (id: string) => void;
  idPrefix: string;
  flat?: boolean;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  function onKey(e: KeyboardEvent<HTMLButtonElement>, i: number) {
    let next = -1;
    if (e.key === 'ArrowRight') next = (i + 1) % items.length;
    else if (e.key === 'ArrowLeft') next = (i - 1 + items.length) % items.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = items.length - 1;
    if (next < 0) return;
    e.preventDefault();
    const item = items[next];
    if (!item) return;
    onSelect(item.id);
    refs.current[next]?.focus();
  }
  return (
    <div role="tablist" aria-label={label} className={`tablist ${flat ? 'flat' : ''}`.trim()}>
      {items.map((t, i) => {
        const on = t.id === selected;
        return (
          <button
            key={t.id}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="tab"
            id={`${idPrefix}-tab-${t.id}`}
            aria-selected={on}
            aria-controls={`${idPrefix}-panel`}
            tabIndex={on ? 0 : -1}
            onClick={() => onSelect(t.id)}
            onKeyDown={(e) => onKey(e, i)}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}

export function tabPanelProps(idPrefix: string, selected: string) {
  return {
    role: 'tabpanel' as const,
    id: `${idPrefix}-panel`,
    'aria-labelledby': `${idPrefix}-tab-${selected}`,
    tabIndex: 0,
  };
}

/** Inline SVG icons. Decorative: always aria-hidden; the text next to them carries the meaning. */
import type { Tone } from '../lib/status';

const base = {
  width: 14,
  height: 14,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2.4,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true,
  focusable: false,
};

export function ToneIcon({ tone }: { tone: Tone }) {
  switch (tone) {
    case 'pass':
      return (
        <svg {...base}>
          <path d="M5 12.5l4.5 4.5L19 7.5" />
        </svg>
      );
    case 'find':
      return (
        <svg {...base}>
          <path d="M4 12.5l4 4L15 9" />
          <path d="M19 6v7M19 17v.5" />
        </svg>
      );
    case 'retry':
      return (
        <svg {...base}>
          <path d="M20 11a8 8 0 1 0-2.3 5.7" />
          <path d="M20 4v7h-7" />
        </svg>
      );
    case 'input':
      return (
        <svg {...base}>
          <path d="M9 9a3 3 0 1 1 4 2.8c-.7.3-1 .9-1 1.7V14" />
          <path d="M12 18v.5" />
        </svg>
      );
    case 'esc':
      return (
        <svg {...base}>
          <path d="M12 4l9 16H3z" />
        </svg>
      );
    case 'abort':
      return (
        <svg {...base}>
          <path d="M6 6l12 12M18 6L6 18" />
        </svg>
      );
    default:
      return (
        <svg {...base}>
          <circle cx="12" cy="12" r="3" />
        </svg>
      );
  }
}

export function SearchIcon({ size = 16 }: { size?: number }) {
  return (
    <svg {...base} width={size} height={size} strokeWidth={2}>
      <circle cx="11" cy="11" r="7" />
      <path d="M20 20l-3.5-3.5" />
    </svg>
  );
}

export function CopyIcon() {
  return (
    <svg {...base} width={16} height={16} strokeWidth={2}>
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15V5a1 1 0 0 1 1-1h10" />
    </svg>
  );
}

export function BlockIcon({
  kind,
}: {
  kind: 'skills' | 'workflows' | 'pods' | 'harness' | 'person';
}) {
  const p = { ...base, width: 20, height: 20, strokeWidth: 2 };
  switch (kind) {
    case 'skills':
      return (
        <svg {...p}>
          <rect x="4" y="4" width="16" height="16" rx="3" />
          <path d="M9 12h6" />
        </svg>
      );
    case 'workflows':
      return (
        <svg {...p}>
          <circle cx="5" cy="12" r="2" />
          <circle cx="12" cy="12" r="2" />
          <circle cx="19" cy="12" r="2" />
          <path d="M7 12h3M14 12h3" />
        </svg>
      );
    case 'pods':
      return (
        <svg {...p}>
          <circle cx="8" cy="9" r="3" />
          <circle cx="16" cy="9" r="3" />
          <path d="M3 19c1-3 3-4 5-4s4 1 5 4M11 19c1-3 3-4 5-4s4 1 5 4" />
        </svg>
      );
    case 'harness':
      return (
        <svg {...p}>
          <path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z" />
          <path d="M8.5 12l2.5 2.5 4.5-5" />
        </svg>
      );
    default:
      return (
        <svg {...p}>
          <circle cx="12" cy="8" r="4" />
          <path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6" />
        </svg>
      );
  }
}

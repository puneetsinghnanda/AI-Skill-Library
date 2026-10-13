import { useState } from 'react';
import { CopyIcon } from './Icons';

/** Monospace command chip, selectable, with a copy button (Doc 4 §2.0.5). */
export function CodeChip({
  code,
  onDark = false,
  copy = true,
}: {
  code: string;
  onDark?: boolean;
  copy?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  async function doCopy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }
  return (
    <span className="row gap-6" style={{ flexWrap: 'nowrap', maxWidth: '100%' }}>
      <code className={`tm-code ${onDark ? 'on-dark' : ''}`.trim()}>{code}</code>
      {copy ? (
        <button
          type="button"
          className={`tm-btn ${onDark ? 'btn-light' : 'btn-ghost'} copy-btn`}
          style={{ padding: '0 12px' }}
          onClick={() => void doCopy()}
          aria-label={`Copy command: ${code}`}
        >
          <CopyIcon />
          <span aria-live="polite" className={copied ? '' : 'sr-only'}>
            {copied ? 'Copied' : ''}
          </span>
        </button>
      ) : null}
    </span>
  );
}

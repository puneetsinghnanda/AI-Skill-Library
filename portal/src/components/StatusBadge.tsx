import type { ReactNode } from 'react';
import type { StatusWord, Tone } from '../lib/status';
import { ToneIcon } from './Icons';

const CLASS: Record<Tone, string> = {
  pass: 'b-pass',
  find: 'b-find',
  retry: 'b-retry',
  input: 'b-input',
  esc: 'b-esc',
  abort: 'b-abort',
  cancel: 'b-cancel',
  navy: 'b-navy',
  teal: 'b-teal',
};

/** A plain badge (role, phase, version...). */
export function Badge({
  tone = 'navy',
  mono = false,
  className = '',
  children,
}: {
  tone?: Tone;
  mono?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span className={`tm-badge ${CLASS[tone]} ${mono ? 'mono' : ''} ${className}`.trim()}>
      {children}
    </span>
  );
}

/** A status: icon plus word, never colour alone (Doc 4 §6.1, TC-POR-007). */
export function StatusBadge({
  status,
  suffix,
  className = '',
}: {
  status: StatusWord;
  suffix?: string;
  className?: string;
}) {
  return (
    <span className={`tm-badge ${CLASS[status.tone]} ${className}`.trim()} data-tone={status.tone}>
      <ToneIcon tone={status.tone} />
      {status.word}
      {suffix ? ` · ${suffix}` : null}
    </span>
  );
}

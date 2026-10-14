import { useEffect, useId, useRef, type ReactNode } from 'react';

/**
 * Confirmation for a destructive admin action (SDD-09 §4.16). Modal `alertdialog`: focus starts on
 * Cancel, Tab stays inside (fields in the body included, such as a row action's reason), Escape
 * cancels, and focus returns to the control that opened it.
 */
export function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel,
  busy = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  confirmLabel: string;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const id = useId();
  const boxRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const cancel = useRef(onCancel);
  cancel.current = onCancel;

  useEffect(() => {
    if (!open) return;
    const back = document.activeElement as HTMLElement | null;
    cancelRef.current?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.preventDefault();
        cancel.current();
        return;
      }
      if (e.key !== 'Tab' || !boxRef.current) return;
      const items = [
        ...boxRef.current.querySelectorAll<HTMLElement>(
          'input:not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled])',
        ),
      ];
      const first = items[0];
      const last = items[items.length - 1];
      if (!first || !last) return;
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      back?.focus?.();
    };
  }, [open]);

  if (!open) return null;
  return (
    <div className="dialog-backdrop">
      <div
        ref={boxRef}
        className="tm-card dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={`${id}-t`}
        aria-describedby={`${id}-d`}
      >
        <h2 className="dialog-title" id={`${id}-t`}>
          {title}
        </h2>
        <div id={`${id}-d`} className="body dialog-body">
          {children}
        </div>
        <div className="row end gap-12 mt-20">
          <button ref={cancelRef} type="button" className="tm-btn btn-ghost" onClick={onCancel}>
            Cancel
          </button>
          <button type="button" className="tm-btn btn-danger" onClick={onConfirm} disabled={busy}>
            {busy ? 'Working…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

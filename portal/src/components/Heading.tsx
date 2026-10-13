import { useEffect, type ReactNode } from 'react';

/**
 * The one h1 per screen (SDD-09 §8). tabIndex -1 lets the shell move focus here on route change.
 * Also sets the document title.
 */
export function PageTitle({
  children,
  title,
  className = 'page-h1',
}: {
  children: ReactNode;
  title: string;
  className?: string;
}) {
  useEffect(() => {
    document.title = `${title} · Truminds AI Skill Library`;
  }, [title]);
  return (
    <h1 className={className} tabIndex={-1}>
      {children}
    </h1>
  );
}

export function SectionHead({
  eyebrow,
  title,
  sub,
  aside,
  id,
}: {
  eyebrow?: string;
  title: string;
  sub?: ReactNode;
  aside?: ReactNode;
  id?: string;
}) {
  const head = (
    <div>
      {eyebrow ? <p className="tm-eyebrow">{eyebrow}</p> : null}
      <h2 className="tm-h2" id={id}>
        {title}
      </h2>
      {sub ? <p className="tm-sub">{sub}</p> : null}
    </div>
  );
  if (!aside) return head;
  return (
    <div className="row between align-end gap-12">
      {head}
      {aside}
    </div>
  );
}

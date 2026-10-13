import {
  useMemo,
  useRef,
  useState,
  type FocusEvent,
  type FormEvent,
  type KeyboardEvent,
} from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { usePods, useSkills } from '../api/queries';
import { useAuth } from '../auth/port';
import { SearchIcon } from '../components/Icons';
import { initials } from '../lib/format';
import { useView } from './ViewContext';

const NAV = [
  { to: '/', label: 'Home', match: (p: string) => p === '/' },
  {
    to: '/how-it-works',
    label: 'How it works',
    match: (p: string) => p.startsWith('/how-it-works'),
  },
  { to: '/skills', label: 'Skills', match: (p: string) => p.startsWith('/skills') },
  { to: '/pods', label: 'Pods', match: (p: string) => p.startsWith('/pods') },
  {
    to: '/insights',
    label: 'Insights',
    match: (p: string) => p.startsWith('/insights') || p.startsWith('/runs'),
  },
  { to: '/get-started', label: 'Get started', match: (p: string) => p.startsWith('/get-started') },
];

/** Active tab: Skill detail -> Skills; Pod detail and builder -> Pods; Run detail -> Insights. */
export function activeNav(pathname: string): string | null {
  return NAV.find((n) => n.match(pathname))?.label ?? null;
}

function Search() {
  const navigate = useNavigate();
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(false);
  const [touched, setTouched] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);
  const skills = useSkills({ limit: 100 }, touched);
  const pods = usePods({ limit: 100 }, touched);
  const needle = q.trim().toLowerCase();
  const results = useMemo(() => {
    if (!needle) return [];
    const s = (skills.data?.data.items ?? [])
      .filter((k) =>
        [k.id, k.title, k.summary, k.agent_role_label, k.phase, ...k.outputs]
          .join(' ')
          .toLowerCase()
          .includes(needle),
      )
      .slice(0, 5)
      .map((k) => ({ to: `/skills/${k.id}`, label: k.title, kind: 'Skill' }));
    const p = (pods.data?.data.items ?? [])
      .filter((x) =>
        [x.title, x.summary ?? '', ...x.agents].join(' ').toLowerCase().includes(needle),
      )
      .slice(0, 3)
      .map((x) => ({ to: `/pods/${x.id}`, label: x.title, kind: 'Pod' }));
    return [...s, ...p];
  }, [needle, skills.data, pods.data]);

  function submit(e: FormEvent) {
    e.preventDefault();
    setOpen(false);
    navigate(needle ? `/skills?q=${encodeURIComponent(q.trim())}` : '/skills');
  }
  function onBlur(e: FocusEvent) {
    if (!boxRef.current?.contains(e.relatedTarget as Node | null)) setOpen(false);
  }
  function onKey(e: KeyboardEvent) {
    if (e.key === 'Escape') setOpen(false);
  }
  return (
    <div className="searchbox" ref={boxRef}>
      <form role="search" aria-label="Site search" onSubmit={submit}>
        <label className="searchbox-field">
          <SearchIcon />
          <span className="sr-only">Search skills, roles, pods</span>
          <input
            type="search"
            value={q}
            placeholder="Search skills, roles, pods"
            onFocus={() => {
              setTouched(true);
              setOpen(true);
            }}
            onChange={(e) => {
              setQ(e.target.value);
              setOpen(true);
            }}
            aria-describedby="topbar-search-count"
            onKeyDown={onKey}
            onBlur={onBlur}
          />
        </label>
      </form>
      <span id="topbar-search-count" className="sr-only" aria-live="polite">
        {open && needle ? `${results.length} suggestions` : ''}
      </span>
      {open && needle && results.length > 0 ? (
        <ul className="plain-list searchbox-results" aria-label="Suggestions">
          {results.map((r) => (
            <li key={r.to}>
              <Link to={r.to} onClick={() => setOpen(false)} onBlur={onBlur} onKeyDown={onKey}>
                <span>{r.label}</span>
                <span className="xsmall text-2">{r.kind}</span>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/** Top bar (board Nav; SDD-09 §4.2). */
export function TopBar() {
  const { pathname } = useLocation();
  const { view, canSwitch, setView, me } = useView();
  const auth = useAuth();
  const qc = useQueryClient();
  const active = activeNav(pathname);
  return (
    <header className="topbar">
      <div className="topbar-inner">
        <Link to="/" className="brand-link" aria-label="Truminds AI Skill Library home">
          <img src="/brand/logo.svg" alt="" width={104} height={30} />
          <span className="brand-name">AI Skill Library</span>
        </Link>
        <nav aria-label="Main" className="mainnav">
          {NAV.map((n) => (
            <Link key={n.to} to={n.to} aria-current={active === n.label ? 'page' : undefined}>
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="topbar-tools">
          <Search />
          {canSwitch ? (
            <div role="group" aria-label="View as" className="segmented">
              <button
                type="button"
                aria-pressed={view === 'business'}
                onClick={() => setView('business')}
              >
                Business
              </button>
              <button
                type="button"
                aria-pressed={view === 'engineer'}
                onClick={() => setView('engineer')}
              >
                Engineer
              </button>
            </div>
          ) : null}
          <div className="userchip">
            <span className="avatar" aria-hidden="true">
              {initials(me.display_name, me.pseudonym)}
            </span>
            <span className="userchip-role">{me.role_label}</span>
            <button
              type="button"
              className="signout"
              onClick={() => {
                qc.clear();
                void auth.signOut();
              }}
            >
              Sign out
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}

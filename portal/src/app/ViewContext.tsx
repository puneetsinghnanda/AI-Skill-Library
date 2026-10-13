/**
 * Business | Engineer view (SDD-09 §3.6). The switch changes the layout only; access is decided by
 * the server on every request. The choice is kept in localStorage `tm.view` as a convenience.
 */
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import type { MeData, RoleName, ViewName } from '../api/types';
import { readLocal, writeLocal } from '../lib/storage';

export const VIEW_KEY = 'tm.view';

interface ViewState {
  view: ViewName;
  canSwitch: boolean;
  setView: (v: ViewName) => void;
  me: MeData;
  hasRole: (...roles: RoleName[]) => boolean;
}

const Ctx = createContext<ViewState | null>(null);

export function initialView(me: MeData): ViewName {
  if (!me.can_switch_view) return me.default_view;
  const stored = readLocal(VIEW_KEY);
  return stored === 'business' || stored === 'engineer' ? stored : me.default_view;
}

export function ViewProvider({ me, children }: { me: MeData; children: ReactNode }) {
  const [chosen, setChosen] = useState<ViewName>(() => initialView(me));
  const view: ViewName = me.can_switch_view ? chosen : me.default_view;
  const setView = useCallback(
    (v: ViewName) => {
      if (!me.can_switch_view) return;
      setChosen(v);
      writeLocal(VIEW_KEY, v);
    },
    [me.can_switch_view],
  );
  const value = useMemo<ViewState>(
    () => ({
      view,
      canSwitch: me.can_switch_view,
      setView,
      me,
      hasRole: (...roles) => me.roles.some((r) => roles.includes(r.role)),
    }),
    [view, me, setView],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useView(): ViewState {
  const v = useContext(Ctx);
  if (!v) throw new Error('ViewProvider is missing');
  return v;
}

/** Roles that may open the SDD-11 improvement report (§5.4): own skill, eng lead, admin. */
export function canOpenImprovement(me: MeData, skillId: string): boolean {
  return me.roles.some(
    (r) =>
      r.role === 'eng_lead' ||
      r.role === 'admin' ||
      (r.role === 'skill_owner' && r.scope === skillId),
  );
}

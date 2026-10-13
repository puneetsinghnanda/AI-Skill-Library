import type { CapabilityMap } from '../api/types';
import { ToneIcon } from './Icons';

/**
 * Capability map: roles x SDLC phases (SDD-09 §6). The server filters pilot skills out of the
 * shared map; the SPA does not filter. Internal maps mark pilot skills with the word "pilot".
 */
export function CapabilityMapTable({ map }: { map: CapabilityMap }) {
  return (
    <div
      className="tm-scroll"
      role="region"
      aria-label="Capability map, scrolls sideways"
      tabIndex={0}
    >
      <table className="tm-table" style={{ minWidth: 900 }}>
        <caption className="sr-only">
          {map.audience === 'shared' ? 'Production skills' : 'Skills'} by role and SDLC phase
        </caption>
        <thead>
          <tr>
            <th scope="col">Role</th>
            {map.phases.map((p) => (
              <th scope="col" key={p.id}>
                {p.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {map.rows.map((r) => (
            <tr key={r.role}>
              <th scope="row">{r.label}</th>
              {map.phases.map((p) => {
                const cells = r.cells[p.id] ?? [];
                return (
                  <td key={p.id}>
                    {cells.length === 0 ? (
                      <span className="sr-only">None</span>
                    ) : (
                      <span className="row gap-6">
                        {cells.map((c) =>
                          c.status === 'pilot' ? (
                            <span key={c.skill_id} className="tm-badge b-input">
                              <ToneIcon tone="input" />
                              {c.title} · pilot
                            </span>
                          ) : (
                            <span key={c.skill_id} className="tm-badge b-teal">
                              {c.evidence_backed ? <ToneIcon tone="pass" /> : null}
                              {c.title}
                              {c.evidence_backed ? (
                                <span className="sr-only">, evidence-backed</span>
                              ) : null}
                            </span>
                          ),
                        )}
                      </span>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

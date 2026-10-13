import type { FlowStep } from '../api/types';

/** Workflow strip: skill steps in white boxes, human gates dashed amber (Doc 4 §2.0.5). */
export function WorkflowStrip({ flow, showIds }: { flow: FlowStep[]; showIds: boolean }) {
  return (
    <ol aria-label="Workflow steps" className="wf-strip">
      {flow.map((f) => (
        <li
          key={`${f.seq}-${f.label}`}
          className={`wf-step ${f.kind === 'gate' ? 'gate' : ''}`.trim()}
        >
          <span className="l">
            {f.kind === 'gate' ? <span className="sr-only">Human gate: </span> : null}
            {f.label}
          </span>
          <span className="w">{f.who}</span>
          {showIds && f.step_id ? <span className="id">{f.step_id}</span> : null}
        </li>
      ))}
    </ol>
  );
}

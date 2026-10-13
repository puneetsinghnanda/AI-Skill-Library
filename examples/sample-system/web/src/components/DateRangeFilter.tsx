import { useState, type FormEvent } from 'react';

interface Props {
  from: string;
  to: string;
  onApply: (range: { from: string; to: string }) => void;
}

export function DateRangeFilter({ from, to, onApply }: Props) {
  const [draftFrom, setDraftFrom] = useState(from);
  const [draftTo, setDraftTo] = useState(to);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    onApply({ from: draftFrom, to: draftTo });
  };

  return (
    <form className="filters" onSubmit={submit}>
      <label>
        From
        <br />
        <input type="date" value={draftFrom} onChange={(e) => setDraftFrom(e.target.value)} />
      </label>
      <label>
        To
        <br />
        <input type="date" value={draftTo} onChange={(e) => setDraftTo(e.target.value)} />
      </label>
      <button type="submit">Apply</button>
    </form>
  );
}

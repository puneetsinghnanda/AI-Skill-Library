import { useEffect, useState } from 'react';

export interface AsyncState<T> {
  data: T | undefined;
  error: string | undefined;
  loading: boolean;
}

/** Runs `load` whenever `key` changes; ignores results that arrive after a newer request. */
export function useAsync<T>(load: () => Promise<T>, key: string): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({ data: undefined, error: undefined, loading: true });

  useEffect(() => {
    let current = true;
    setState((s) => ({ ...s, loading: true, error: undefined }));
    load().then(
      (data) => current && setState({ data, error: undefined, loading: false }),
      (err: unknown) =>
        current && setState({ data: undefined, error: err instanceof Error ? err.message : String(err), loading: false }),
    );
    return () => {
      current = false;
    };
    // `load` is recreated on each render; `key` captures its inputs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return state;
}

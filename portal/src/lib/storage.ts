/** localStorage for per-viewer conveniences only (the view choice, SDD-09 §3.6). Never tokens. */
export function readLocal(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function writeLocal(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* storage blocked: the choice is simply not remembered */
  }
}

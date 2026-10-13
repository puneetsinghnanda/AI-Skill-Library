import { USERS, type DemoUserId } from '../mocks/fixtures';
import { scenario } from '../mocks/handlers';
import { TEST_AUTH_MARKER } from './fixtureAuth';

export const DEMO_USER_KEY = 'tm.demo.user';
export const DEMO_BEHIND_KEY = 'tm.demo.behind';
export const DEMO_EMPTY_KEY = 'tm.demo.empty';

function store(key: string, value: string | null) {
  try {
    if (value === null) window.sessionStorage.removeItem(key);
    else window.sessionStorage.setItem(key, value);
  } catch {
    /* ignore */
  }
}

/** Demo mode only: says the data is illustrative and lets a reviewer switch the signed-in user. */
export function DemoBanner({ user }: { user: DemoUserId }) {
  return (
    <aside
      className="demo-banner tm-card"
      aria-label="Demo mode"
      data-fixture={TEST_AUTH_MARKER}
      style={{ borderRadius: 0, borderWidth: '0 0 1px 0', padding: '8px 0' }}
    >
      <div className="tm-wrap row between gap-12">
        <span className="row gap-8">
          <span className="tm-badge b-demo">Illustrative data</span>
          <span className="small text-2">
            Demo mode: invented data, no sign-in. Not for client use.
          </span>
        </span>
        <span className="row gap-12">
          <label className="field small">
            Demo user
            <select
              value={user}
              onChange={(e) => {
                store(DEMO_USER_KEY, e.target.value);
                window.location.assign('/');
              }}
            >
              {Object.values(USERS).map((u) => (
                <option key={u.id} value={u.id}>
                  {u.label}
                </option>
              ))}
            </select>
          </label>
          <label className="toggle small">
            <input
              type="checkbox"
              checked={scenario.behind}
              onChange={(e) => {
                store(DEMO_BEHIND_KEY, e.target.checked ? '1' : null);
                window.location.reload();
              }}
            />
            Insights behind
          </label>
        </span>
      </div>
    </aside>
  );
}

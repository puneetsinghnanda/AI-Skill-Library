import { useStatus } from '../api/queries';
import { env } from '../config/env';
import { localTime } from '../lib/format';

/** "Insights are behind" banner (SDD-09 §3.6, TC-POR-005). The page keeps showing the last data. */
export function StatusBanner() {
  const { data } = useStatus();
  const behind = data?.data.behind === true;
  return (
    <div role="status" aria-live="polite">
      {behind ? (
        <div className="status-banner">
          <div className="tm-wrap">
            Insights are behind; last event received at{' '}
            <time dateTime={data?.data.last_event_received_at ?? undefined}>
              {localTime(data?.data.last_event_received_at) ?? 'an unknown time'}
            </time>
            .
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function isTestEnvironment(...values: (string | null | undefined)[]): boolean {
  return values.some((v) => v?.trim().toLowerCase() === 'test');
}

/** The banner itself; shown on every screen of a test environment (ADR 0006). */
export function TestEnvironmentNotice() {
  return (
    <div className="test-env-banner" role="note" aria-label="Test environment">
      <div className="tm-wrap">
        <strong>TEST ENVIRONMENT</strong> · Data here is for testing only. Sign-in is the interim
        test setup.
      </div>
    </div>
  );
}

/** Shown when the build says ENVIRONMENT=test, or GET /v1/status reports `environment: test`. */
export function TestEnvironmentBanner() {
  const { data } = useStatus();
  return isTestEnvironment(env.environment, data?.data.environment) ? (
    <TestEnvironmentNotice />
  ) : null;
}

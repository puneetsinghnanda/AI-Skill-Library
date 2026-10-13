"""0001_initial: roles, the full SDD-08 §10.2 schema, maintenance functions, grants.

Revision ID: 0001_initial
Revises:
Forward-only (SDD-08 §11.1).
"""

from __future__ import annotations

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

ROLES = """
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'insights_app') THEN
    CREATE ROLE insights_app NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'insights_read') THEN
    CREATE ROLE insights_read NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'insights_reveal') THEN
    CREATE ROLE insights_reveal NOLOGIN;
  END IF;
END $$;
"""

DDL = """
-- ===== Organisation and people =====
CREATE TABLE users (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        uuid NOT NULL,
  sso_subject      uuid NOT NULL,
  pseudonym        text NOT NULL UNIQUE CHECK (pseudonym ~ '^eng-[0-9a-f]{4,8}$'),
  display_name_enc bytea, email_enc bytea, email_hmac bytea, enc_key_id text,
  agent_role       text,
  app_roles        text[] NOT NULL DEFAULT '{}',
  roles_synced_at  timestamptz,
  github_login     text,
  active           boolean NOT NULL DEFAULT true,
  created_at       timestamptz NOT NULL DEFAULT now(),
  erased_at        timestamptz,
  UNIQUE (tenant_id, sso_subject));

CREATE TABLE clients (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code text NOT NULL UNIQUE CHECK (code ~ '^CL-[0-9A-Z]{2,8}$'),
  display_name_enc bytea NOT NULL,
  consent_ref text, consent_recorded_at timestamptz,
  consent_scope text[] NOT NULL DEFAULT '{}',
  consent_withdrawn_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now());

CREATE TABLE projects (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id uuid NOT NULL REFERENCES clients,
  code text NOT NULL UNIQUE CHECK (code ~ '^PRJ-[0-9A-Z]{2,8}$'));

CREATE TABLE systems (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid NOT NULL REFERENCES projects,
  code text NOT NULL UNIQUE CHECK (code ~ '^SYS-[0-9A-Z]{2,8}$'),
  domain text NOT NULL,
  companion_repo text NOT NULL,
  pack_status text NOT NULL DEFAULT 'missing' CHECK (pack_status IN ('fresh','stale','missing')),
  pack_signed_at timestamptz, pack_signed_by uuid REFERENCES users,
  pack_drift_files int, pack_status_at timestamptz,
  lifecycle_state text NOT NULL DEFAULT 'PROVISIONED',
  archived_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now());

CREATE TABLE system_repos (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  system_id uuid NOT NULL REFERENCES systems,
  name text NOT NULL,
  github_full_name text NOT NULL,
  kind text NOT NULL CHECK (kind IN ('product','read_only')),
  UNIQUE (system_id, name), UNIQUE (system_id, github_full_name));
CREATE INDEX ON system_repos (github_full_name);

CREATE TABLE role_grants (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users,
  role text NOT NULL CHECK (role IN ('viewer','engineer','tech_lead','skill_owner','stage_approver','eng_lead','admin')),
  scope_type text NOT NULL CHECK (scope_type IN ('org','client','project','system','skill','stage')),
  scope_id text,
  granted_at timestamptz NOT NULL, revoked_at timestamptz, granted_by uuid REFERENCES users);
CREATE UNIQUE INDEX role_grants_active ON role_grants (user_id, role, scope_type, coalesce(scope_id,''))
  WHERE revoked_at IS NULL;

CREATE TABLE keys (
  key_id text PRIMARY KEY CHECK (key_id ~ '^key_[0-9A-HJKMNP-TV-Z]{26}$'),
  user_id uuid NOT NULL REFERENCES users,
  device_id text NOT NULL CHECK (device_id ~ '^dev_[0-9A-HJKMNP-TV-Z]{26}$'),
  device_label text CHECK (char_length(device_label) <= 40),
  public_key bytea NOT NULL CHECK (octet_length(public_key) = 32),
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz,
  revoked_reason text CHECK (revoked_reason IN ('replaced','user_request','offboarded','admin_other','lost_device','compromised')),
  compromised_since timestamptz,
  revoked_by uuid REFERENCES users,
  revoke_note text CHECK (char_length(revoke_note) <= 200));
CREATE UNIQUE INDEX keys_one_active ON keys (user_id, device_id) WHERE revoked_at IS NULL;

CREATE TABLE signature_anchors (
  sha256      text PRIMARY KEY CHECK (sha256 ~ '^[0-9a-f]{64}$'),
  kind        text NOT NULL CHECK (kind IN ('verification','approval','pack','eval')),
  key_id      text NOT NULL REFERENCES keys,
  event_id    text NOT NULL,
  anchored_at timestamptz NOT NULL);

CREATE TABLE devices (
  device_id text PRIMARY KEY, user_id uuid NOT NULL REFERENCES users,
  os text, plugin_version text, tsl_version text,
  outbox_depth int, outbox_oldest_at timestamptz,
  first_seen_at timestamptz NOT NULL, last_seen_at timestamptz NOT NULL, last_session_id text);

CREATE TABLE ingest_tokens (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind text NOT NULL CHECK (kind IN ('otel','ci')),
  token_sha256 bytea NOT NULL UNIQUE, label text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(), revoked_at timestamptz, last_used_at timestamptz);

CREATE TABLE github_hooks (
  hook_id bigint PRIMARY KEY,
  target text NOT NULL,
  secret_enc bytea NOT NULL, enc_key_id text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(), revoked_at timestamptz);

-- ===== Catalogue (synced from the marketplace repo, §6.4) =====
CREATE TABLE catalogue_releases (
  tag text PRIMARY KEY, plugin_version text NOT NULL, tsl_version text NOT NULL,
  commit_sha text NOT NULL, released_at timestamptz NOT NULL, synced_at timestamptz NOT NULL,
  notes jsonb NOT NULL DEFAULT '[]');

CREATE TABLE skills (
  id text PRIMARY KEY,
  agent_role text NOT NULL CHECK (agent_role IN ('business-analyst','solution-architect','developer',
             'qa-engineer','devops','security','ux-designer','delivery-manager')),
  title text NOT NULL, summary text NOT NULL,
  phase text NOT NULL CHECK (phase IN ('requirements','design','build','test','operate')),
  domains text[] NOT NULL DEFAULT '{}',
  owner_pseudonym text, current_version text);

CREATE TABLE skill_versions (
  skill_id text NOT NULL REFERENCES skills, version text NOT NULL,
  status text NOT NULL CHECK (status IN ('draft','pilot','production','deprecated')),
  inputs jsonb NOT NULL, outputs jsonb NOT NULL, context_sections jsonb NOT NULL DEFAULT '[]',
  size_budget_tokens int, allowed_tools text[] NOT NULL DEFAULT '{}',
  portal jsonb NOT NULL DEFAULT '{}',
  changelog text, release_tag text REFERENCES catalogue_releases,
  eval_cases int, eval_pass_rate numeric(4,3), eval_key_id text REFERENCES keys, eval_recorded_at timestamptz,
  published_at timestamptz,
  PRIMARY KEY (skill_id, version));

CREATE TABLE workflows (id text PRIMARY KEY, title text NOT NULL, current_version text);
CREATE TABLE workflow_versions (
  workflow_id text NOT NULL REFERENCES workflows, version text NOT NULL,
  definition jsonb NOT NULL, step_count int NOT NULL, published_at timestamptz,
  PRIMARY KEY (workflow_id, version));
CREATE TABLE workflow_steps (
  workflow_id text NOT NULL, version text NOT NULL, seq int NOT NULL,
  step_id text NOT NULL, kind text NOT NULL CHECK (kind IN ('skill','gate','pr')),
  skill_id text REFERENCES skills, skill_range text, gate_role text,
  PRIMARY KEY (workflow_id, version, seq),
  FOREIGN KEY (workflow_id, version) REFERENCES workflow_versions);

CREATE TABLE pods (
  id text PRIMARY KEY, title text NOT NULL,
  kind text NOT NULL CHECK (kind IN ('brownfield','greenfield','quality','ux')),
  status text NOT NULL CHECK (status IN ('draft','pilot','production','deprecated')),
  owner_pseudonym text,
  current_version text);
CREATE TABLE pod_versions (
  pod_id text NOT NULL REFERENCES pods, version text NOT NULL,
  status text NOT NULL CHECK (status IN ('draft','pilot','production','deprecated')),
  definition jsonb NOT NULL,
  source_sha text NOT NULL,
  published_at timestamptz, PRIMARY KEY (pod_id, version));
CREATE TABLE pod_agents (
  pod_id text NOT NULL, version text NOT NULL, agent_key text NOT NULL,
  role text NOT NULL, display_name text NOT NULL, engineers int NOT NULL,
  PRIMARY KEY (pod_id, version, agent_key),
  FOREIGN KEY (pod_id, version) REFERENCES pod_versions);
CREATE TABLE pod_agent_skills (
  pod_id text NOT NULL, version text NOT NULL, agent_key text NOT NULL, skill_id text NOT NULL REFERENCES skills,
  skill_range text NOT NULL, cross_role boolean NOT NULL DEFAULT false,
  PRIMARY KEY (pod_id, version, agent_key, skill_id),
  FOREIGN KEY (pod_id, version, agent_key) REFERENCES pod_agents);
CREATE TABLE pod_workflows (
  pod_id text NOT NULL, version text NOT NULL, workflow_id text NOT NULL, workflow_range text NOT NULL,
  PRIMARY KEY (pod_id, version, workflow_id),
  FOREIGN KEY (pod_id, version) REFERENCES pod_versions);

-- ===== Runs (projected from events) =====
CREATE TABLE runs (
  id text PRIMARY KEY CHECK (id ~ '^run_[0-9A-HJKMNP-TV-Z]{26}$'),
  system_id uuid REFERENCES systems, project_id uuid REFERENCES projects,
  workflow_id text, workflow_version text, pod_id text REFERENCES pods, pod_version text,
  ticket_ref text, user_id uuid REFERENCES users,
  status text CHECK (status IN ('RUNNING','PAUSED_INPUT','PAUSED_APPROVAL','COMPLETED')),
  end_reason text CHECK (end_reason IN ('pr_opened','completed','aborted','rejected','cancelled','lock_released','archived')),
  end_code text,
  current_step_id text, current_seq int, lowest_band text CHECK (lowest_band IN ('High','Medium','Low')),
  plugin_version text, pack_fresh boolean,
  started_at timestamptz, status_changed_at timestamptz, completed_at timestamptz, updated_at timestamptz,
  is_partial boolean NOT NULL DEFAULT false);
CREATE INDEX ON runs (system_id, updated_at DESC);
CREATE INDEX ON runs (user_id, status);
CREATE INDEX ON runs (pod_id, started_at);
CREATE INDEX runs_open ON runs (project_id, status) WHERE status <> 'COMPLETED';

CREATE TABLE run_sessions (
  run_id text NOT NULL REFERENCES runs, session_id text NOT NULL,
  first_seen_at timestamptz NOT NULL, last_seen_at timestamptz NOT NULL,
  PRIMARY KEY (run_id, session_id));
CREATE INDEX ON run_sessions (session_id);

CREATE TABLE steps (
  run_id text NOT NULL REFERENCES runs, step_id text NOT NULL, attempt int NOT NULL CHECK (attempt >= 1),
  seq int, skill_id text, skill_version text,
  attempt_cause text,
  started_at timestamptz, decided_at timestamptz,
  outcome text CHECK (outcome IN ('PASS','PASS-WITH-FINDINGS','RETRY','NEEDS-INPUT','ESCALATE','ABORT')),
  band text CHECK (band IN ('High','Medium','Low')),
  signals jsonb, reasons text[] NOT NULL DEFAULT '{}', caps text[] NOT NULL DEFAULT '{}',
  gate_failures text[] NOT NULL DEFAULT '{}',
  findings_blocker int, findings_major int, findings_minor int,
  duration_ms int, tokens_in bigint, tokens_out bigint, cost_usd numeric(10,4),
  PRIMARY KEY (run_id, step_id, attempt),
  FOREIGN KEY (skill_id, skill_version) REFERENCES skill_versions);
CREATE INDEX ON steps (skill_id, skill_version, decided_at);
CREATE INDEX steps_first ON steps (decided_at) WHERE attempt = 1;

CREATE TABLE check_records (
  run_id text NOT NULL, step_id text NOT NULL, attempt int NOT NULL,
  verification_sha256 text NOT NULL, key_id text REFERENCES keys,
  decided_by text NOT NULL, decided_at timestamptz NOT NULL,
  findings_dropped text[] NOT NULL DEFAULT '{}',
  ci_verified boolean,
  PRIMARY KEY (run_id, step_id, attempt),
  FOREIGN KEY (run_id, step_id, attempt) REFERENCES steps);

CREATE TABLE questions (
  run_id text NOT NULL REFERENCES runs, question_id text NOT NULL, step_id text,
  blocking boolean, ask_role text, evidence_ref text,
  created_at timestamptz, answered_at timestamptz, accepted_default boolean,
  PRIMARY KEY (run_id, question_id));
CREATE INDEX questions_open ON questions (run_id) WHERE answered_at IS NULL;

CREATE TABLE approvals (
  run_id text NOT NULL REFERENCES runs, gate text NOT NULL, step_id text,
  reason_code text, requested_at timestamptz,
  decision text CHECK (decision IN ('approve','reject','changes')),
  approver_user_id uuid REFERENCES users, approver_role text, recorded_at timestamptz,
  PRIMARY KEY (run_id, gate));
CREATE INDEX approvals_open ON approvals (run_id) WHERE recorded_at IS NULL;

CREATE TABLE pull_requests (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  repo_id uuid NOT NULL REFERENCES system_repos, number int NOT NULL, run_id text REFERENCES runs,
  state text NOT NULL CHECK (state IN ('open','closed','merged')), draft boolean,
  head_sha text, lowest_band text,
  opened_at timestamptz, merged_at timestamptz, closed_at timestamptz,
  review_count int NOT NULL DEFAULT 0, first_review_at timestamptz,
  changes_requested boolean NOT NULL DEFAULT false, review_comments int NOT NULL DEFAULT 0,
  UNIQUE (repo_id, number));
CREATE INDEX ON pull_requests (run_id);
CREATE INDEX ON pull_requests (merged_at);
CREATE INDEX ON pull_requests (head_sha);

CREATE TABLE ci_checks (
  repo_id uuid NOT NULL REFERENCES system_repos, head_sha text NOT NULL, number int,
  result text NOT NULL CHECK (result IN ('pass','fail')), codes text[] NOT NULL DEFAULT '{}',
  source text NOT NULL CHECK (source IN ('event','webhook')), checked_at timestamptz NOT NULL,
  PRIMARY KEY (repo_id, head_sha, source));

CREATE TABLE run_usage (
  run_id text PRIMARY KEY REFERENCES runs,
  tokens_in bigint NOT NULL DEFAULT 0, tokens_out bigint NOT NULL DEFAULT 0,
  cost_usd numeric(12,4) NOT NULL DEFAULT 0, active_s bigint NOT NULL DEFAULT 0);

-- ===== Raw intake =====
CREATE TABLE event_ids (event_id text PRIMARY KEY, received_at timestamptz NOT NULL);
CREATE INDEX ON event_ids (received_at);

CREATE TABLE events_raw (
  event_id text NOT NULL, received_at timestamptz NOT NULL DEFAULT now(),
  occurred_at timestamptz NOT NULL, clock_skew boolean NOT NULL DEFAULT false,
  type text NOT NULL, schema_version int NOT NULL, run_id text,
  user_id uuid, source text NOT NULL CHECK (source IN ('tsl','ci')),
  body jsonb NOT NULL,
  projected_at timestamptz, projection_error text, retry_after timestamptz,
  PRIMARY KEY (event_id, received_at)
) PARTITION BY RANGE (received_at);
CREATE INDEX events_unprojected ON events_raw (occurred_at) WHERE projected_at IS NULL;
CREATE INDEX ON events_raw (run_id, occurred_at);
CREATE INDEX ON events_raw (type, received_at);

-- PostgreSQL 16 does not allow identity columns on partitioned tables (added in 17), so the
-- SDD-08 "GENERATED ALWAYS AS IDENTITY" id is a sequence default here.
CREATE SEQUENCE otel_events_id_seq AS bigint;
CREATE TABLE otel_events (
  id bigint NOT NULL DEFAULT nextval('otel_events_id_seq'), received_at timestamptz NOT NULL DEFAULT now(),
  signal text NOT NULL CHECK (signal IN ('metric','log')), name text NOT NULL,
  ts timestamptz NOT NULL, session_id text, run_id text,
  value double precision, attributes jsonb NOT NULL DEFAULT '{}',
  PRIMARY KEY (id, received_at)
) PARTITION BY RANGE (received_at);
ALTER SEQUENCE otel_events_id_seq OWNED BY otel_events.id;
CREATE INDEX ON otel_events (session_id, ts);

CREATE TABLE webhook_deliveries (
  delivery_id text PRIMARY KEY, event text NOT NULL, action text,
  repo_full_name text, received_at timestamptz NOT NULL DEFAULT now(), result text NOT NULL);

-- ===== Counters maintained by the projector (incremented once per event) =====
CREATE TABLE user_daily (day date, user_id uuid, system_id uuid, runs_started int DEFAULT 0, steps_decided int DEFAULT 0,
  PRIMARY KEY (day, user_id, system_id));
CREATE TABLE hook_daily (day date, system_id uuid, hook text, decision text, code text, n int DEFAULT 0,
  PRIMARY KEY (day, system_id, hook, decision, code));
CREATE TABLE ingest_daily (day date, type text, source text, n int DEFAULT 0, PRIMARY KEY (day, type, source));
CREATE TABLE pr_unlinked_daily (day date, github_full_name text, opened int DEFAULT 0, PRIMARY KEY (day, github_full_name));

-- ===== Long-term rollups (written before retention deletes base rows) =====
CREATE TABLE agg_monthly (
  month date, project_id uuid, system_id uuid, skill_id text, skill_version text, workflow_id text, pod_id text,
  metric text, value numeric NOT NULL,
  PRIMARY KEY (month, project_id, system_id, skill_id, skill_version, workflow_id, pod_id, metric));
CREATE TABLE agg_user_month (month date, user_id uuid, PRIMARY KEY (month, user_id));

-- ===== Support =====
CREATE TABLE cause_labels (code text PRIMARY KEY, label text NOT NULL);
CREATE TABLE view_refresh_log (view_name text PRIMARY KEY, refreshed_at timestamptz NOT NULL, duration_ms int NOT NULL);
CREATE TABLE audit_log (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, at timestamptz NOT NULL DEFAULT now(),
  actor_user_id uuid NOT NULL, action text NOT NULL,
  target_type text, target text,
  before jsonb, after jsonb, reason text,
  detail jsonb NOT NULL DEFAULT '{}');
"""

# Maintenance functions. The worker runs as insights_app, which does not own tables, so the few
# owner-only operations it needs (partition DDL, materialized view refresh, audit_log purge) go
# through SECURITY DEFINER functions with fixed allowlists. Registry §7 lists them.
FUNCTIONS = r"""
CREATE FUNCTION insights_ensure_partition(p_table text, p_month date) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
  m date := date_trunc('month', p_month)::date;
  part text;
BEGIN
  IF p_table NOT IN ('events_raw', 'otel_events') THEN
    RAISE EXCEPTION 'not a partitioned table: %', p_table;
  END IF;
  part := p_table || '_' || to_char(m, 'YYYYMM');
  IF to_regclass(part) IS NOT NULL THEN
    RETURN false;
  END IF;
  EXECUTE format('CREATE TABLE %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)',
                 part, p_table, m, (m + interval '1 month')::date);
  RETURN true;
END $$;

CREATE FUNCTION insights_drop_partitions_before(p_table text, p_before date) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
  r record;
  n integer := 0;
  upper_bound date;
BEGIN
  IF p_table NOT IN ('events_raw', 'otel_events') THEN
    RAISE EXCEPTION 'not a partitioned table: %', p_table;
  END IF;
  FOR r IN
    SELECT c.relname FROM pg_inherits i
    JOIN pg_class c ON c.oid = i.inhrelid
    JOIN pg_class p ON p.oid = i.inhparent
    WHERE p.relname = p_table AND c.relname ~ ('^' || p_table || '_[0-9]{6}$')
  LOOP
    upper_bound := (to_date(right(r.relname, 6), 'YYYYMM') + interval '1 month')::date;
    IF upper_bound <= p_before THEN
      EXECUTE format('DROP TABLE %I', r.relname);
      n := n + 1;
    END IF;
  END LOOP;
  RETURN n;
END $$;

CREATE FUNCTION insights_partitions_ahead(p_table text) RETURNS integer
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT count(*)::int FROM pg_inherits i
  JOIN pg_class c ON c.oid = i.inhrelid JOIN pg_class p ON p.oid = i.inhparent
  WHERE p.relname = p_table AND c.relname ~ ('^' || p_table || '_[0-9]{6}$')
    AND to_date(right(c.relname, 6), 'YYYYMM') > date_trunc('month', now())::date
$$;

CREATE FUNCTION insights_refresh_view(p_view text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_matviews WHERE schemaname = 'public' AND matviewname = p_view) THEN
    RAISE EXCEPTION 'not a materialized view: %', p_view;
  END IF;
  EXECUTE format('REFRESH MATERIALIZED VIEW CONCURRENTLY %I', p_view);
END $$;

-- audit_log is append-only for insights_app (SEC-T-28). Retention deletes only rows older than
-- the configured period (RD-4) and never anything younger than 24 months.
CREATE FUNCTION insights_purge_audit_log(p_before timestamptz) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE n integer;
BEGIN
  IF p_before > now() - interval '24 months' THEN
    RAISE EXCEPTION 'audit_log retention may not be shorter than 24 months';
  END IF;
  DELETE FROM audit_log WHERE at < p_before;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n;
END $$;

-- Grants (SDD-08 §9.4), re-applied by every migration so new tables are covered.
CREATE FUNCTION insights_apply_grants() RETURNS void
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
DECLARE
  r record;
  no_read text[] := ARRAY['events_raw','otel_events','ingest_tokens','github_hooks','webhook_deliveries',
                          'users','audit_log','alembic_version'];
BEGIN
  FOR r IN SELECT c.relname, c.relkind FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE n.nspname = 'public' AND c.relkind IN ('r','p','v','m') AND NOT c.relispartition
  LOOP
    IF r.relname = 'audit_log' THEN
      EXECUTE format('GRANT SELECT, INSERT ON %I TO insights_app', r.relname);
    ELSIF r.relkind IN ('r','p') THEN
      EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON %I TO insights_app', r.relname);
    ELSE
      EXECUTE format('GRANT SELECT ON %I TO insights_app', r.relname);
    END IF;
    IF NOT (r.relname = ANY (no_read)) THEN
      EXECUTE format('GRANT SELECT ON %I TO insights_read', r.relname);
    END IF;
  END LOOP;
  -- Read role: users without the encrypted columns.
  REVOKE ALL ON users FROM insights_read;
  GRANT SELECT (id, tenant_id, sso_subject, pseudonym, agent_role, app_roles, roles_synced_at,
                github_login, active, created_at, erased_at) ON users TO insights_read;
  REVOKE ALL ON clients FROM insights_read;
  GRANT SELECT (id, code, consent_ref, consent_recorded_at, consent_scope, consent_withdrawn_at, created_at)
    ON clients TO insights_read;
  -- Reveal role: the audited name path only (SDD-09 §5.3).
  REVOKE ALL ON users FROM insights_reveal;
  GRANT SELECT (id, display_name_enc, enc_key_id, erased_at) ON users TO insights_reveal;
  GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO insights_app;
  GRANT EXECUTE ON FUNCTION insights_ensure_partition(text, date), insights_drop_partitions_before(text, date),
        insights_partitions_ahead(text), insights_refresh_view(text), insights_purge_audit_log(timestamptz)
        TO insights_app;
  GRANT USAGE ON SCHEMA public TO insights_app, insights_read, insights_reveal;
END $$;
REVOKE EXECUTE ON FUNCTION insights_ensure_partition(text, date), insights_drop_partitions_before(text, date),
       insights_partitions_ahead(text), insights_refresh_view(text), insights_purge_audit_log(timestamptz),
       insights_apply_grants() FROM PUBLIC;
"""


def _exec(sql: str) -> None:
    """Run raw SQL on the migration connection (no placeholder parsing; PL/pgSQL uses %)."""
    cur = op.get_bind().connection.dbapi_connection.cursor()  # type: ignore[union-attr]
    try:
        cur.execute(sql)
    finally:
        cur.close()


def upgrade() -> None:
    _exec(ROLES)
    _exec(DDL)
    _exec(FUNCTIONS)
    _exec("SELECT insights_apply_grants()")


def downgrade() -> None:
    raise RuntimeError("Migrations are forward-only (SDD-08 §11.1); fix with a new migration.")

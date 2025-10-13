-- === Emberlog DB Migration -> 1.1.0 ===========================
-- Purpose: Notifications MVP (Outbox + Subs + Deliveries)
-- Idempotent-ish: uses IF NOT EXISTS where supported.

BEGIN;

-- 1) Outbox (FIFO-style) — single, simple queue for new incidents
CREATE TABLE IF NOT EXISTS outbox_incidents (
  id             bigserial PRIMARY KEY,
  incident_id    bigint NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
  created_at     timestamptz NOT NULL DEFAULT now(),
  -- Processing bookkeeping (optional but handy for safe retries)
  status         text NOT NULL DEFAULT 'pending',      -- pending|processing|done|dead
  attempts       integer NOT NULL DEFAULT 0,
  last_error     text,
  next_attempt_at timestamptz
);

-- Prevent dup enqueue for the same incident unless you WANT multi-event semantics
CREATE UNIQUE INDEX IF NOT EXISTS uq_outbox_incidents_incident
  ON outbox_incidents(incident_id) WHERE status IN ('pending','processing');

-- FIFO + poll efficiency
CREATE INDEX IF NOT EXISTS idx_outbox_incidents_pending_fifo
  ON outbox_incidents (status, COALESCE(next_attempt_at, created_at), id);

-- 2) Subscriptions — who gets notified, about what, and how
-- Transport examples: 'webhook', 'sms', 'email', 'console'
-- Filters are simple ANDed fields; leave null to mean "no filter"
CREATE TABLE IF NOT EXISTS notification_subscriptions (
  id               bigserial PRIMARY KEY,
  name             text NOT NULL,
  is_active        boolean NOT NULL DEFAULT true,
  transport        text NOT NULL,        -- e.g., webhook|sms|email|console
  target_config    jsonb NOT NULL,       -- e.g., {url, headers}, {phone}, {email}, etc.

  -- Simple filters (MVP). Null = wildcard.
  channel          text,                 -- exact match
  incident_type    text,                 -- exact match
  units_any        text[],               -- intersect on ANY of these units
  keyword_ilike    text,                 -- case-insensitive substring on transcript/original_text

  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_notif_subs_active ON notification_subscriptions(is_active);
CREATE INDEX IF NOT EXISTS idx_notif_subs_channel ON notification_subscriptions(channel);
CREATE INDEX IF NOT EXISTS idx_notif_subs_incident_type ON notification_subscriptions(incident_type);
CREATE INDEX IF NOT EXISTS idx_notif_subs_units_any ON notification_subscriptions USING gin(units_any);
-- keyword_ilike is evaluated at runtime; if it becomes hot we can materialize tsvectors per policy later.

-- 3) Deliveries — audit trail + retry tracking
CREATE TABLE IF NOT EXISTS notification_deliveries (
  id               bigserial PRIMARY KEY,
  subscription_id  bigint NOT NULL REFERENCES notification_subscriptions(id) ON DELETE CASCADE,
  incident_id      bigint NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
  transport        text NOT NULL,             -- denormalized for quick glance
  status           text NOT NULL,             -- sent|failed|skipped|retrying
  attempt_no       integer NOT NULL DEFAULT 1,
  response_code    integer,                   -- HTTP status or provider code
  response_meta    jsonb,                     -- headers, body snippet, provider ids, etc.
  error_message    text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  sent_at          timestamptz
);

CREATE INDEX IF NOT EXISTS idx_deliveries_by_incident ON notification_deliveries(incident_id);
CREATE INDEX IF NOT EXISTS idx_deliveries_by_sub ON notification_deliveries(subscription_id);
CREATE INDEX IF NOT EXISTS idx_deliveries_status ON notification_deliveries(status);

-- 4) Optional: DB-enforced outbox insert via trigger (COMMENTED OUT)
--    If you later want to guarantee an enqueue from any writer of incidents,
--    uncomment this block. For now the API will do it in the same tx.
-- DO $$
-- BEGIN
--   IF NOT EXISTS (
--     SELECT 1 FROM pg_proc p
--     JOIN pg_namespace n ON n.oid = p.pronamespace
--     WHERE p.proname = 'tg_incidents_outbox_enqueue'
--   ) THEN
--     CREATE FUNCTION tg_incidents_outbox_enqueue() RETURNS trigger AS $f$
--     BEGIN
--       INSERT INTO outbox_incidents (incident_id) VALUES (NEW.id)
--       ON CONFLICT DO NOTHING;
--       RETURN NEW;
--     END;
--     $f$ LANGUAGE plpgsql;
--
--     CREATE TRIGGER trg_incidents_after_insert
--       AFTER INSERT ON incidents
--       FOR EACH ROW EXECUTE FUNCTION tg_incidents_outbox_enqueue();
--   END IF;
-- END $$;

-- 5) Schema version flip
UPDATE schema_version SET active = false WHERE active = true;
INSERT INTO schema_version (version, active) VALUES ('1.1.0', true);

COMMIT;

BEGIN;

-- 1) incident_outbox: enforce NOT NULL + default on next_attempt_at
ALTER TABLE incident_outbox
  ALTER COLUMN next_attempt_at SET DEFAULT now();

ALTER TABLE incident_outbox
  ALTER COLUMN next_attempt_at SET NOT NULL;

-- 1a) Optional: rename legacy sequence/index names for clarity
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'outbox_incidents_id_seq') THEN
    EXECUTE 'ALTER SEQUENCE outbox_incidents_id_seq RENAME TO incident_outbox_id_seq';
  END IF;

  IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'outbox_incidents_pkey') THEN
    EXECUTE 'ALTER INDEX outbox_incidents_pkey RENAME TO incident_outbox_pkey';
  END IF;
END $$;

-- 2) deliveries: add status index + a helpful “queue” scheduler index
CREATE INDEX IF NOT EXISTS idx_deliveries_status
  ON deliveries(status);

CREATE INDEX IF NOT EXISTS idx_deliveries_queue_sched
  ON deliveries(status, COALESCE(next_attempt_at, created_at))
  WHERE status = 'queued';

-- 3) De-dup endpoints: prevent duplicate channels per user/type/address
CREATE UNIQUE INDEX IF NOT EXISTS uq_notification_channels_user_type_addr
  ON notification_channels(user_id, type, address);

-- 4) alert_rules: require non-empty channels array
ALTER TABLE alert_rules
  ADD CONSTRAINT chk_alert_rules_channels_nonempty
  CHECK (jsonb_typeof(channels) = 'array' AND jsonb_array_length(channels) > 0)
  NOT VALID;

-- You can validate in a low-traffic window:
-- ALTER TABLE alert_rules VALIDATE CONSTRAINT chk_alert_rules_channels_nonempty;

-- 5) Version bump (optional; if you track every patch)
UPDATE schema_version SET active = false WHERE active = true;
INSERT INTO schema_version (version, active) VALUES ('1.3.1', true);

COMMIT;

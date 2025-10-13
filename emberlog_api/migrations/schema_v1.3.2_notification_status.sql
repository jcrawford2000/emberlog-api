BEGIN;

-- 1) incident_outbox: enforce NOT NULL + default on next_attempt_at
ALTER TABLE incident_outbox
  ADD COLUMN status text NOT NULL DEFAULT 'pending';

ALTER TABLE incident_outbox
  ADD COLUMN available_at timestamptz NOT NULL DEFAULT now();

ALTER TABLE incident_outbox
  ADD COLUMN event_type text NOT NULL;

UPDATE schema_version SET active = false WHERE active = true;
INSERT INTO schema_version (version, active) VALUES ('1.3.2', true);

COMMIT;

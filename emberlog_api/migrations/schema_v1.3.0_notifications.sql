BEGIN;

-- Ensure pgcrypto for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 0) Bump-safe users table to match design (adds columns if missing)
--    If users doesn't exist, create it per design.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='users') THEN
    CREATE TABLE users (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      auth_provider TEXT NOT NULL,              -- 'firebase'
      external_sub  TEXT NOT NULL UNIQUE,       -- Firebase uid
      email         TEXT,
      phone_e164    TEXT,
      display_name  TEXT,
      created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
    );
  ELSE
    -- Add missing cols if prior minimal users existed
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='id') THEN
      ALTER TABLE users ADD COLUMN id UUID PRIMARY KEY DEFAULT gen_random_uuid();
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='auth_provider') THEN
      ALTER TABLE users ADD COLUMN auth_provider TEXT;
      UPDATE users SET auth_provider='firebase' WHERE auth_provider IS NULL;
      ALTER TABLE users ALTER COLUMN auth_provider SET NOT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='external_sub') THEN
      ALTER TABLE users ADD COLUMN external_sub TEXT;
      -- You may need to backfill this from your auth system; keep nullable until app sets it.
      -- ALTER TABLE users ALTER COLUMN external_sub SET NOT NULL;
      -- ALTER TABLE users ADD CONSTRAINT uq_users_external_sub UNIQUE (external_sub);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='phone_e164') THEN
      ALTER TABLE users ADD COLUMN phone_e164 TEXT;
    END IF;

    -- created_at/updated_at safety
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='created_at') THEN
      ALTER TABLE users ADD COLUMN created_at TIMESTAMPTZ NOT NULL DEFAULT now();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='updated_at') THEN
      ALTER TABLE users ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now();
    END IF;
  END IF;
END $$;

-- 1) Notification channel enums & table (delivery endpoints)
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='channel_type') THEN
    CREATE TYPE channel_type AS ENUM ('web','sms','email','webhook');
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS notification_channels (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type channel_type NOT NULL,
  address TEXT,                               -- +16025551212 / a@b.com / https://...
  is_verified BOOLEAN NOT NULL DEFAULT FALSE,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb, -- e.g. webhook secret, friendly name
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_channels_user ON notification_channels(user_id);

-- 2) Alert rules (filters + which channels to use)
CREATE TABLE IF NOT EXISTS alert_rules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  filters JSONB NOT NULL,                      -- v1: { "call_types":[], "units":[], "keywords":[], "talkgroups":[] }
  channels JSONB NOT NULL,                     -- e.g. [{"channel_id":"..."}]
  throttle_sec INT,                            -- null = no throttle
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_alert_rules_user ON alert_rules(user_id);
CREATE INDEX IF NOT EXISTS idx_alert_rules_enabled ON alert_rules(enabled);
-- jsonb_path_ops is efficient for containment/path queries; default GIN also ok.
CREATE INDEX IF NOT EXISTS idx_alert_rules_filters_gin ON alert_rules USING GIN (filters jsonb_path_ops);

-- 3) Deliveries (audit of each send)
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='delivery_status') THEN
    CREATE TYPE delivery_status AS ENUM ('queued','sent','failed','throttled','skipped');
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS deliveries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  alert_rule_id UUID NOT NULL REFERENCES alert_rules(id) ON DELETE CASCADE,
  incident_id BIGINT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
  channel_id UUID NOT NULL REFERENCES notification_channels(id) ON DELETE CASCADE,
  status delivery_status NOT NULL DEFAULT 'queued',
  attempts INT NOT NULL DEFAULT 0,
  last_error TEXT,
  provider_message_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  next_attempt_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_deliveries_incident ON deliveries(incident_id);
CREATE INDEX IF NOT EXISTS idx_deliveries_rule ON deliveries(alert_rule_id);
CREATE INDEX IF NOT EXISTS idx_deliveries_status ON deliveries(status);

-- 4) Transactional outbox (rename/reshape if the old table exists)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='outbox_incidents') THEN
    -- Drop duplicate-protection index if it exists
    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname='uq_outbox_incidents_incident') THEN
      DROP INDEX uq_outbox_incidents_incident;
    END IF;

    ALTER TABLE outbox_incidents RENAME TO incident_outbox;

    -- Converge to design: payload jsonb, attempts, next_attempt_at, last_error; remove 'status'
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='incident_outbox' AND column_name='payload') THEN
      ALTER TABLE incident_outbox ADD COLUMN payload JSONB NOT NULL DEFAULT '{}'::jsonb;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='incident_outbox' AND column_name='next_attempt_at') THEN
      ALTER TABLE incident_outbox ADD COLUMN next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now();
    END IF;

    -- status is not part of the design; keep attempts + last_error
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='incident_outbox' AND column_name='status') THEN
      ALTER TABLE incident_outbox DROP COLUMN status;
    END IF;

  ELSE
    -- Fresh create matching the design
    CREATE TABLE incident_outbox (
      id BIGSERIAL PRIMARY KEY,
      incident_id BIGINT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
      payload JSONB NOT NULL,                      -- denormalized incident subset
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      attempts INT NOT NULL DEFAULT 0,
      next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      last_error TEXT
    );
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_incident_outbox_sched ON incident_outbox(next_attempt_at);

-- 5) One-time data migration from previous MVP tables (if they exist)
--    - notification_subscriptions -> users/notification_channels/alert_rules
--    - notification_deliveries    -> deliveries
DO $$
DECLARE
  has_subs    BOOLEAN := EXISTS (SELECT 1 FROM information_schema.tables  WHERE table_name='notification_subscriptions');
  has_delivs  BOOLEAN := EXISTS (SELECT 1 FROM information_schema.tables  WHERE table_name='notification_deliveries');
  has_user_id BOOLEAN := EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='notification_subscriptions' AND column_name='user_id');
  sys_user UUID;
BEGIN
  -- Ensure a system user for orphaned/migrated subs
  SELECT id INTO sys_user FROM users WHERE external_sub='system';
  IF sys_user IS NULL THEN
    INSERT INTO users (id, auth_provider, external_sub, email, display_name)
    VALUES (gen_random_uuid(), 'system', 'system', 'system@emberlog', 'System')
    RETURNING id INTO sys_user;
  END IF;

  IF has_subs THEN
    -- Create channels from distinct (uid, transport, target) tuples
    IF has_user_id THEN
      WITH src AS (
        SELECT
          COALESCE(ns.user_id, sys_user) AS uid,
          ns.transport,
          (ns.target_config->>'url')   AS url,
          (ns.target_config->>'phone') AS phone,
          (ns.target_config->>'email') AS email,
          ns.id AS sub_id
        FROM notification_subscriptions ns
      ),
      chosen AS (
        SELECT DISTINCT
          uid,
          CASE
            WHEN transport='webhook' THEN 'webhook'
            WHEN transport='sms' THEN 'sms'
            WHEN transport='email' THEN 'email'
            ELSE 'web'
          END::channel_type AS ctype,
          COALESCE(url, phone, email) AS address
        FROM src
      )
      INSERT INTO notification_channels (id, user_id, type, address, is_verified, metadata)
      SELECT gen_random_uuid(), uid, ctype, address, false, '{}'::jsonb
      FROM chosen
      WHERE address IS NOT NULL
      ON CONFLICT DO NOTHING;
    ELSE
      -- No user_id in subscriptions (pre-1.2): attach everything to system user
      WITH src AS (
        SELECT
          'web'::text AS transport,
          (ns.target_config->>'url')   AS url,
          (ns.target_config->>'phone') AS phone,
          (ns.target_config->>'email') AS email,
          ns.id AS sub_id
        FROM notification_subscriptions ns
      ),
      chosen AS (
        SELECT DISTINCT
          sys_user AS uid,
          CASE
            WHEN transport='webhook' THEN 'webhook'
            WHEN transport='sms' THEN 'sms'
            WHEN transport='email' THEN 'email'
            ELSE 'web'
          END::channel_type AS ctype,
          COALESCE(url, phone, email) AS address
        FROM src
      )
      INSERT INTO notification_channels (id, user_id, type, address, is_verified, metadata)
      SELECT gen_random_uuid(), uid, ctype, address, false, '{}'::jsonb
      FROM chosen
      WHERE address IS NOT NULL
      ON CONFLICT DO NOTHING;
    END IF;

    -- Map subscription -> channel_id
    DROP TABLE IF EXISTS _tmp_sub_channel_map;
    CREATE TEMP TABLE _tmp_sub_channel_map (sub_id BIGINT PRIMARY KEY, channel_id UUID NOT NULL);

    IF has_user_id THEN
      INSERT INTO _tmp_sub_channel_map (sub_id, channel_id)
      SELECT s.sub_id,
             (SELECT nc.id
                FROM notification_channels nc
               WHERE nc.user_id = s.uid
                 AND nc.type = CASE
                                 WHEN s.transport='webhook' THEN 'webhook'
                                 WHEN s.transport='sms' THEN 'sms'
                                 WHEN s.transport='email' THEN 'email'
                                 ELSE 'web'
                               END::channel_type
                 AND nc.address = COALESCE(s.url, s.phone, s.email)
               LIMIT 1)
      FROM (
        SELECT
          ns.id AS sub_id,
          COALESCE(ns.user_id, sys_user) AS uid,
          ns.transport,
          (ns.target_config->>'url')   AS url,
          (ns.target_config->>'phone') AS phone,
          (ns.target_config->>'email') AS email
        FROM notification_subscriptions ns
      ) s
      WHERE COALESCE(s.url, s.phone, s.email) IS NOT NULL;
    ELSE
      INSERT INTO _tmp_sub_channel_map (sub_id, channel_id)
      SELECT ns.id AS sub_id,
             (SELECT nc.id
                FROM notification_channels nc
               WHERE nc.user_id = sys_user
                 AND nc.type = CASE
                                 WHEN ns.transport='webhook' THEN 'webhook'
                                 WHEN ns.transport='sms' THEN 'sms'
                                 WHEN ns.transport='email' THEN 'email'
                                 ELSE 'web'
                               END::channel_type
                 AND nc.address = COALESCE(ns.target_config->>'url', ns.target_config->>'phone', ns.target_config->>'email')
               LIMIT 1)
      FROM notification_subscriptions ns
      WHERE COALESCE(ns.target_config->>'url', ns.target_config->>'phone', ns.target_config->>'email') IS NOT NULL;
    END IF;

    -- Create alert_rules (single-channel per old subscription)
    IF has_user_id THEN
      INSERT INTO alert_rules (id, user_id, name, enabled, filters, channels)
      SELECT gen_random_uuid(),
             COALESCE(ns.user_id, sys_user) AS user_id,
             COALESCE(ns.name, CONCAT('Migrated sub ', ns.id::text)) AS name,
             ns.is_active AS enabled,
             jsonb_strip_nulls(
               jsonb_build_object(
                 'call_types', CASE WHEN ns.incident_type IS NOT NULL THEN jsonb_build_array(ns.incident_type) ELSE '[]'::jsonb END,
                 'units',      COALESCE(to_jsonb(ns.units_any), '[]'::jsonb),
                 'keywords',   CASE WHEN ns.keyword_ilike IS NOT NULL THEN jsonb_build_array(ns.keyword_ilike) ELSE '[]'::jsonb END,
                 'talkgroups', CASE WHEN ns.channel IS NOT NULL THEN jsonb_build_array(ns.channel) ELSE '[]'::jsonb END
               )
             ) AS filters,
             jsonb_build_array(jsonb_build_object('channel_id', m.channel_id::text)) AS channels
      FROM notification_subscriptions ns
      JOIN _tmp_sub_channel_map m ON m.sub_id = ns.id;
    ELSE
      INSERT INTO alert_rules (id, user_id, name, enabled, filters, channels)
      SELECT gen_random_uuid(),
             sys_user AS user_id,
             COALESCE(ns.name, CONCAT('Migrated sub ', ns.id::text)) AS name,
             ns.is_active AS enabled,
             jsonb_strip_nulls(
               jsonb_build_object(
                 'call_types', CASE WHEN ns.incident_type IS NOT NULL THEN jsonb_build_array(ns.incident_type) ELSE '[]'::jsonb END,
                 'units',      COALESCE(to_jsonb(ns.units_any), '[]'::jsonb),
                 'keywords',   CASE WHEN ns.keyword_ilike IS NOT NULL THEN jsonb_build_array(ns.keyword_ilike) ELSE '[]'::jsonb END,
                 'talkgroups', CASE WHEN ns.channel IS NOT NULL THEN jsonb_build_array(ns.channel) ELSE '[]'::jsonb END
               )
             ) AS filters,
             jsonb_build_array(jsonb_build_object('channel_id', m.channel_id::text)) AS channels
      FROM notification_subscriptions ns
      JOIN _tmp_sub_channel_map m ON m.sub_id = ns.id;
    END IF;
  END IF;

  IF has_delivs THEN
    -- Migrate deliveries
    INSERT INTO deliveries (id, alert_rule_id, incident_id, channel_id, status, attempts, last_error,
                            provider_message_id, created_at, updated_at, next_attempt_at)
    SELECT gen_random_uuid(),
           ar.id,
           nd.incident_id,
           m.channel_id,
           CASE
             WHEN nd.status IN ('sent','retrying') THEN 'sent'
             WHEN nd.status IN ('failed') THEN 'failed'
             WHEN nd.status IN ('pending','processing') THEN 'queued'
             ELSE 'queued'
           END::delivery_status,
           GREATEST(1, nd.attempt_no),
           nd.error_message,
           (nd.response_meta->>'provider_message_id'),
           nd.created_at,
           COALESCE(nd.sent_at, nd.created_at),
           NULL
    FROM notification_deliveries nd
    JOIN notification_subscriptions ns ON ns.id = nd.subscription_id
    JOIN _tmp_sub_channel_map m ON m.sub_id = ns.id
    JOIN alert_rules ar
      ON ar.user_id = CASE WHEN has_user_id THEN COALESCE(ns.user_id, sys_user) ELSE sys_user END
     AND ar.name = COALESCE(ns.name, CONCAT('Migrated sub ', ns.id::text));
  END IF;
END $$;

-- 6) Optional: drop legacy MVP tables after successful migration
--     (Comment these out until you verify data)
-- DROP TABLE IF EXISTS notification_deliveries;
-- DROP TABLE IF EXISTS notification_subscriptions;

-- 7) Version bump
UPDATE schema_version SET active = false WHERE active = true;
INSERT INTO schema_version (version, active) VALUES ('1.3.0', true);

COMMIT;

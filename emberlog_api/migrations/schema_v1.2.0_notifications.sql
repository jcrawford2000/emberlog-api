-- Case-insensitive text for emails
CREATE EXTENSION IF NOT EXISTS citext;

BEGIN;

-- 1) Users (minimal now; expand later with auth provider IDs)
CREATE TABLE IF NOT EXISTS users (
  id           bigserial PRIMARY KEY,
  email        citext NOT NULL UNIQUE,
  display_name text NOT NULL,
  tz           text NOT NULL DEFAULT 'America/Phoenix',
  is_active    boolean NOT NULL DEFAULT true,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);

-- 2) Tie subscriptions to a user (owner)
ALTER TABLE notification_subscriptions
  ADD COLUMN IF NOT EXISTS user_id bigint;

ALTER TABLE notification_subscriptions
  ADD CONSTRAINT fk_notif_subs_user
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- 3) Indexing & a default safety net
CREATE INDEX IF NOT EXISTS idx_notif_subs_user ON notification_subscriptions(user_id);

-- Optional: backfill a system user and attach existing subs (if any)
-- INSERT INTO users (email, display_name) VALUES ('system@emberlog', 'System') ON CONFLICT DO NOTHING;
-- UPDATE notification_subscriptions SET user_id = (SELECT id FROM users WHERE email='system@emberlog')
-- WHERE user_id IS NULL;

-- 4) Bump schema version
UPDATE schema_version SET active = false WHERE active = true;
INSERT INTO schema_version (version, active) VALUES ('1.2.0', true);

COMMIT;

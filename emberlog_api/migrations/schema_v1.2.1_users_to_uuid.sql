BEGIN;

-- Needed for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1) Add a new UUID column on users (if missing) to become the new PK
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS id_new UUID DEFAULT gen_random_uuid();

-- Backfill any NULLs (paranoia)
UPDATE users SET id_new = gen_random_uuid() WHERE id_new IS NULL;

-- (No FK will reference id_new yet; no need to add UNIQUE here.)

-- 2) If MVP table exists, migrate its user FK column from BIGINT -> UUID
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='notification_subscriptions') THEN
    -- Add staging UUID column if needed
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='notification_subscriptions' AND column_name='user_id_uuid') THEN
      ALTER TABLE notification_subscriptions
        ADD COLUMN user_id_uuid UUID;
    END IF;

    -- If old bigint column exists, copy mapping into UUID staging column
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name='notification_subscriptions' AND column_name='user_id'
                 AND data_type IN ('bigint','integer')) THEN

      -- Drop old FK if any (name best-effort)
      BEGIN
        ALTER TABLE notification_subscriptions DROP CONSTRAINT fk_notif_subs_user;
      EXCEPTION WHEN undefined_object THEN
        -- ignore
      END;

      -- Drop old index if present
      BEGIN
        DROP INDEX idx_notif_subs_user;
      EXCEPTION WHEN undefined_object THEN
        -- ignore
      END;

      -- Copy bigint -> uuid via users.id -> users.id_new
      UPDATE notification_subscriptions ns
         SET user_id_uuid = u.id_new
        FROM users u
       WHERE ns.user_id IS NOT NULL
         AND u.id = ns.user_id;

      -- Replace bigint column with the uuid one
      ALTER TABLE notification_subscriptions DROP COLUMN user_id;
      ALTER TABLE notification_subscriptions RENAME COLUMN user_id_uuid TO user_id;
    END IF;

    -- If user_id already exists and is UUID, we won't touch it.
  END IF;
END $$;

-- 3) Swap the primary key on users from bigint(id) -> uuid(id_new)
--    Do this safely by discovering the PK constraint name dynamically.
DO $$
DECLARE
  pk_name text;
BEGIN
  SELECT conname
  INTO pk_name
  FROM pg_constraint
  WHERE conrelid = 'users'::regclass
    AND contype = 'p'
  LIMIT 1;

  IF pk_name IS NOT NULL THEN
    EXECUTE format('ALTER TABLE users DROP CONSTRAINT %I', pk_name);
  END IF;
END $$;

-- Drop old bigint id and rename id_new -> id
-- (If you've already run this once, guard each step.)
DO $$
BEGIN
  -- Only drop the old id column if it still exists and is NOT uuid
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'users' AND column_name = 'id'
      AND data_type <> 'uuid'
  ) THEN
    ALTER TABLE users DROP COLUMN id;
  END IF;

  -- Only rename if id_new column still exists
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'users' AND column_name = 'id_new'
  ) THEN
    ALTER TABLE users RENAME COLUMN id_new TO id;
  END IF;

  -- Ensure the new id column is the PK
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'users'::regclass
      AND contype = 'p'
  ) THEN
    ALTER TABLE users ADD PRIMARY KEY (id);
  END IF;
END $$;

-- 4) Now that users.id is UUID PK, add FK/index on notification_subscriptions.user_id (if table/column exist)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='notification_subscriptions')
     AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='notification_subscriptions' AND column_name='user_id') THEN

    -- Ensure type is UUID (if not, you may have skipped earlier steps)
    -- This cast is safe only if column is already uuid; else you'd need USING clause.
    -- We'll just assert it's uuid by checking catalog:
    IF EXISTS (
      SELECT 1
      FROM information_schema.columns
      WHERE table_name='notification_subscriptions' AND column_name='user_id' AND udt_name='uuid'
    ) THEN
      -- Recreate FK (best-effort drop first)
      BEGIN
        ALTER TABLE notification_subscriptions DROP CONSTRAINT fk_notif_subs_user;
      EXCEPTION WHEN undefined_object THEN
        -- ignore
      END;

      ALTER TABLE notification_subscriptions
        ADD CONSTRAINT fk_notif_subs_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

      CREATE INDEX IF NOT EXISTS idx_notif_subs_user
        ON notification_subscriptions(user_id);
    END IF;
  END IF;
END $$;

COMMIT;

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gin;

CREATE TABLE IF NOT EXISTS incidents (
  id                bigserial PRIMARY KEY,
  dispatched_at     timestamptz NOT NULL,
  special_call      boolean NOT NULL DEFAULT false,
  units             text[],
  channel           text,
  incident_type     text,
  address           text,
  source_audio      text NOT NULL,
  original_text     text,
  transcript        text,
  parsed            jsonb,
  created_at        timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT unique_src_idx UNIQUE (source_audio, original_text)
);

ALTER TABLE incidents
ADD COLUMN IF NOT EXISTS fts tsvector
  GENERATED ALWAYS AS (
    setweight(to_tsvector('english', coalesce(incident_type,'')), 'A') ||
    setweight(to_tsvector('english', coalesce(address,'')), 'B') ||
    setweight(to_tsvector('english', coalesce(transcript,'')), 'C')
  ) STORED;
CREATE INDEX IF NOT EXISTS gin_incidents_fts ON incidents USING gin (fts);


CREATE INDEX IF NOT EXISTS idx_incidents_dispatched_at
  ON incidents (dispatched_at DESC);

-- Full-text-ish search over address/incident_type/transcript (fast LIKE/fuzzy)
CREATE INDEX IF NOT EXISTS gin_incidents_trgm
  ON incidents USING gin ((coalesce(address,'') || ' ' || coalesce(incident_type,'') || ' ' || coalesce(transcript,'')) gin_trgm_ops);

-- JSON search (e.g., parsed->'units', parsed->'incident_type')
CREATE INDEX IF NOT EXISTS gin_incidents_parsed
  ON incidents USING gin (parsed);

-- Example: quick view for the last 30 minutes (nice for your web UI)
CREATE OR REPLACE VIEW recent_incidents AS
SELECT *
FROM incidents
WHERE dispatched_at >= now() - interval '30 minutes'
ORDER BY dispatched_at DESC;

CREATE TABLE IF NOT EXISTS schema_version (
  id                serial PRIMARY KEY,
  version           text NOT NULL,
  active            boolean NOT NULL,
  created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX one_active_version
ON schema_version ((active))
WHERE active;

UPDATE schema_version set active=false;
INSERT INTO schema_version (version, active) values ('1.0.0', true);

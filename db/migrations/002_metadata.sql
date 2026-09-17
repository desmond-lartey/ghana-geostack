-- 002_metadata.sql
-- The registry. Every table in core and analysis must have a row in
-- meta.dataset before it is published, and the QC step refuses to pass
-- anything that does not.

BEGIN;

CREATE TABLE IF NOT EXISTS meta.dataset (
    id                text PRIMARY KEY,               -- matches sources.yml id, or <schema>.<table>
    schema_name       text NOT NULL,
    table_name        text NOT NULL,
    title             text NOT NULL,
    theme             text NOT NULL,
    description       text,

    -- Provenance. Without these three a dataset cannot be published.
    source_name       text NOT NULL,
    source_url        text,
    licence           text NOT NULL,
    attribution       text NOT NULL,

    -- Spatial characteristics.
    srid              integer NOT NULL,
    geometry_type     text,
    bbox              geometry(Polygon, 4326),
    spatial_resolution text,                          -- '10 m', '100 m', 'vector'

    -- Temporal characteristics.
    valid_from        date,
    valid_to          date,
    collected_at      date,

    -- Housekeeping.
    feature_count     bigint,
    steward           text,                           -- who to ask when it looks wrong
    sensitivity       text NOT NULL DEFAULT 'public'
                      CHECK (sensitivity IN ('public','restricted','internal')),
    publishable       boolean NOT NULL DEFAULT false, -- false until licence is cleared
    source_checksum   text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),

    UNIQUE (schema_name, table_name)
);

COMMENT ON COLUMN meta.dataset.publishable IS
  'Gate for tiles and public exports. Set true only when the licence has been '
  'read and the attribution string is correct. Default false is deliberate.';

COMMENT ON COLUMN meta.dataset.sensitivity IS
  'restricted covers anything that could identify a household or an '
  'individual facility user. Restricted data is never tiled at high zoom and '
  'never exported to the public bucket.';

CREATE INDEX IF NOT EXISTS dataset_bbox_idx  ON meta.dataset USING GIST (bbox);
CREATE INDEX IF NOT EXISTS dataset_theme_idx ON meta.dataset (theme);

-- ── Lineage ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS meta.lineage (
    id           bigserial PRIMARY KEY,
    dataset_id   text NOT NULL REFERENCES meta.dataset(id) ON DELETE CASCADE,
    derived_from text NOT NULL,                       -- dataset id or external URL
    step         text NOT NULL,                       -- the script that did it
    sql_hash     text,
    run_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS lineage_dataset_idx ON meta.lineage (dataset_id);

-- ── Quality control ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS meta.qc_run (
    id          bigserial PRIMARY KEY,
    started_at  timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    git_sha     text,
    passed      boolean,
    note        text
);

CREATE TABLE IF NOT EXISTS meta.qc_result (
    id          bigserial PRIMARY KEY,
    run_id      bigint NOT NULL REFERENCES meta.qc_run(id) ON DELETE CASCADE,
    check_name  text NOT NULL,
    target      text NOT NULL,                        -- schema.table being checked
    severity    text NOT NULL CHECK (severity IN ('error','warning','info')),
    passed      boolean NOT NULL,
    observed    numeric,
    expected    text,
    detail      text,
    checked_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS qc_result_run_idx ON meta.qc_result (run_id, passed);

-- Latest verdict per table, which is what the README badge and the agent read.
CREATE OR REPLACE VIEW meta.qc_latest AS
SELECT r.target,
       count(*)                                 AS checks_run,
       count(*) FILTER (WHERE NOT r.passed)     AS failures,
       count(*) FILTER (WHERE NOT r.passed
                        AND r.severity = 'error') AS errors,
       max(r.checked_at)                        AS last_checked
FROM meta.qc_result r
JOIN (SELECT max(id) AS id FROM meta.qc_run) latest ON r.run_id = latest.id
GROUP BY r.target;

-- ── Keep updated_at honest ─────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION meta.touch_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS dataset_touch ON meta.dataset;
CREATE TRIGGER dataset_touch BEFORE UPDATE ON meta.dataset
    FOR EACH ROW EXECUTE FUNCTION meta.touch_updated_at();

COMMIT;

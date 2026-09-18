-- 04_land_suitability.sql
-- Weighted multi-criteria siting score on the H3 r7 grid.
--
-- Suitability scores are the easiest thing in GIS to fake authority with. A
-- number between 0 and 100 looks objective and is entirely a product of the
-- weights someone chose. So the weights live in one visible table at the top
-- of this file, every criterion is scored 0-100 on its own before weighting,
-- and the output keeps the component scores alongside the total. If anyone
-- disagrees with the result they can see exactly which weight to argue about.
--
-- The worked example here is siting for off-grid solar mini-grids, which is a
-- live question in the Northern, Savannah, Upper East and Upper West regions.
-- Change the weights to ask a different question; the machinery is the same.

\set ON_ERROR_STOP on
SET search_path TO analysis, h3, core, public;

-- ── The weights. Argue here, not with the map. ─────────────────────────────

DROP TABLE IF EXISTS analysis.suitability_weight;
CREATE TABLE analysis.suitability_weight (
    criterion   text PRIMARY KEY,
    weight      numeric NOT NULL CHECK (weight BETWEEN 0 AND 1),
    direction   text NOT NULL CHECK (direction IN ('higher_better','lower_better')),
    rationale   text NOT NULL
);

INSERT INTO analysis.suitability_weight VALUES
 ('demand',       0.35, 'higher_better',
  'Households without a grid connection are the point of a mini-grid. Proxied '
  'by building count in the cell.'),
 ('grid_distance', 0.25, 'higher_better',
  'Far from existing transmission means the grid is unlikely to arrive soon, '
  'which is what makes off-grid the right answer rather than a stopgap.'),
 ('terrain',      0.15, 'lower_better',
  'Steep ground raises installation cost. Mild penalty only - most of Ghana '
  'is flat enough that this rarely decides anything.'),
 ('road_access',  0.15, 'higher_better',
  'Equipment has to be trucked in and maintained. No road, no mini-grid.'),
 ('flood',        0.10, 'lower_better',
  'Do not site infrastructure on ground that has been under water.');

-- Weights must sum to 1, or the score is not on a 0-100 scale and comparisons
-- across runs are meaningless.
DO $$
DECLARE total numeric;
BEGIN
    SELECT sum(weight) INTO total FROM analysis.suitability_weight;
    IF abs(total - 1.0) > 0.001 THEN
        RAISE EXCEPTION 'Suitability weights sum to %, expected 1.0', total;
    END IF;
END
$$;

-- ── Component scores, each normalised to 0-100 ─────────────────────────────

DROP TABLE IF EXISTS analysis.site_suitability;
CREATE TABLE analysis.site_suitability AS
WITH base AS (
    SELECT
        d.h3,
        d.geom,
        d.region_id,
        d.building_count,
        -- Distance to the nearest primary road, from the hex centre.
        (SELECT ST_Distance(ST_Transform(ST_Centroid(d.geom), 32630),
                            ST_Transform(r.geom, 32630))
         FROM core.road r
         WHERE r.class IN ('motorway','trunk','primary','secondary')
         ORDER BY ST_Centroid(d.geom) <-> r.geom
         LIMIT 1) AS road_dist_m,
        -- Mean slope across the cell.
        (SELECT (ST_SummaryStats(ST_Clip(s.rast, d.geom, true))).mean
         FROM core.slope s
         WHERE ST_Intersects(s.rast, d.geom)
         LIMIT 1) AS mean_slope_deg,
        -- Share of the cell's buildings sitting in a flood-prone zone.
        coalesce((SELECT count(*)::numeric
                  FROM analysis.building_flood_exposure e
                  WHERE ST_Intersects(e.geom, d.geom)), 0)
            / nullif(d.building_count, 0) * 100 AS pct_flood_exposed
    FROM h3.building_density_r7 d
    WHERE d.building_count >= 10        -- ignore empty bush
),
bounds AS (
    -- Percentile bounds rather than min/max, so one outlier cell cannot
    -- compress the whole scale.
    SELECT
        percentile_cont(0.95) WITHIN GROUP (ORDER BY building_count) AS p95_buildings,
        percentile_cont(0.95) WITHIN GROUP (ORDER BY road_dist_m)    AS p95_road,
        percentile_cont(0.95) WITHIN GROUP (ORDER BY mean_slope_deg) AS p95_slope
    FROM base
),
scored AS (
    SELECT
        b.h3,
        b.geom,
        b.region_id,
        b.building_count,
        b.road_dist_m,
        b.mean_slope_deg,
        b.pct_flood_exposed,

        least(100, b.building_count / nullif(x.p95_buildings, 0) * 100)
            AS demand_score,

        -- No grid layer yet, so road distance stands in for remoteness. When
        -- core.transmission_line lands, swap this for real grid distance and
        -- the rest of the file is unchanged.
        least(100, b.road_dist_m / nullif(x.p95_road, 0) * 100)
            AS grid_distance_score,

        greatest(0, 100 - least(100, coalesce(b.mean_slope_deg, 0)
                                     / nullif(x.p95_slope, 0) * 100))
            AS terrain_score,

        -- Road access peaks in the 1-10 km band: on top of a trunk road the
        -- grid will probably reach you anyway; beyond 10 km, logistics bite.
        CASE
            WHEN b.road_dist_m IS NULL   THEN 0
            WHEN b.road_dist_m <  1000   THEN 70
            WHEN b.road_dist_m <= 10000  THEN 100
            WHEN b.road_dist_m <= 25000  THEN 50
            ELSE 15
        END::numeric AS road_access_score,

        greatest(0, 100 - coalesce(b.pct_flood_exposed, 0) * 2)
            AS flood_score
    FROM base b CROSS JOIN bounds x
)
SELECT
    s.*,
    round((
        s.demand_score        * (SELECT weight FROM analysis.suitability_weight WHERE criterion = 'demand')
      + s.grid_distance_score * (SELECT weight FROM analysis.suitability_weight WHERE criterion = 'grid_distance')
      + s.terrain_score       * (SELECT weight FROM analysis.suitability_weight WHERE criterion = 'terrain')
      + s.road_access_score   * (SELECT weight FROM analysis.suitability_weight WHERE criterion = 'road_access')
      + s.flood_score         * (SELECT weight FROM analysis.suitability_weight WHERE criterion = 'flood')
    )::numeric, 1) AS suitability_score
FROM scored s;

ALTER TABLE analysis.site_suitability ADD PRIMARY KEY (h3);
CREATE INDEX site_suit_geom_idx  ON analysis.site_suitability USING GIST (geom);
CREATE INDEX site_suit_score_idx ON analysis.site_suitability (suitability_score DESC);

-- ── Validation ─────────────────────────────────────────────────────────────

SELECT 'cells scored'        AS check, count(*)::text AS value FROM analysis.site_suitability
UNION ALL
SELECT 'score out of range',  count(*)::text FROM analysis.site_suitability
       WHERE suitability_score < 0 OR suitability_score > 100
UNION ALL
SELECT 'median score',        round(percentile_cont(0.5) WITHIN GROUP (ORDER BY suitability_score)::numeric, 1)::text
       FROM analysis.site_suitability
UNION ALL
SELECT 'cells above 75',      count(*)::text FROM analysis.site_suitability WHERE suitability_score > 75
UNION ALL
SELECT 'null road distance',  count(*)::text FROM analysis.site_suitability WHERE road_dist_m IS NULL;

-- Top candidates, with the components visible so the ranking can be checked
-- rather than trusted.
SELECT h3, region_id, building_count,
       round(road_dist_m::numeric) AS road_m,
       demand_score, grid_distance_score, road_access_score,
       terrain_score, flood_score, suitability_score
FROM analysis.site_suitability
ORDER BY suitability_score DESC
LIMIT 20;

-- Sanity check: if the top 20 are all in Greater Accra, the demand weight is
-- swamping everything and the result is just a population map. That is a real
-- answer to a different question.

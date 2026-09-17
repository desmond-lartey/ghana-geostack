-- Tests for the Ghana helper functions. Run against a migrated database.
-- Any failure raises and aborts, which fails CI.

\set ON_ERROR_STOP on

DO $$
DECLARE
    accra  geometry := ST_SetSRID(ST_Point(-0.187, 5.603), 4326);
    tamale geometry := ST_SetSRID(ST_Point(-0.839, 9.403), 4326);
    d      double precision;
    a      double precision;
BEGIN
    -- The bbox must contain Ghana's cities and exclude its neighbours' capitals.
    IF NOT ST_Contains(core.gh_bbox(), accra) THEN
        RAISE EXCEPTION 'gh_bbox does not contain Accra';
    END IF;
    IF ST_Contains(core.gh_bbox(), ST_SetSRID(ST_Point(3.379, 6.524), 4326)) THEN
        RAISE EXCEPTION 'gh_bbox wrongly contains Lagos';
    END IF;

    -- Accra to Tamale is about 420 km in a straight line. A helper that
    -- returns degrees instead of metres would give roughly 3.8 here, which is
    -- exactly the error this test exists to catch.
    d := core.gh_distance_m(accra, tamale) / 1000;
    IF d < 380 OR d > 460 THEN
        RAISE EXCEPTION 'gh_distance_m returned % km for Accra-Tamale, expected ~420', round(d::numeric, 1);
    END IF;

    -- A 1 km buffer should have an area near pi square kilometres.
    a := core.gh_area_m2(core.gh_buffer_m(accra, 1000)) / 1e6;
    IF a < 3.0 OR a > 3.3 THEN
        RAISE EXCEPTION 'gh_area_m2 of a 1 km buffer returned % km2, expected ~3.14', round(a::numeric, 3);
    END IF;

    -- Name normalisation must collapse the real spelling variants.
    IF core.gh_normalise_name('Sekondi-Takoradi') <> core.gh_normalise_name('Sekondi Takoradi') THEN
        RAISE EXCEPTION 'gh_normalise_name does not collapse hyphen variants';
    END IF;
    IF core.gh_normalise_name('  GREATER ACCRA  ') <> 'greater accra' THEN
        RAISE EXCEPTION 'gh_normalise_name does not trim and lowercase';
    END IF;

    -- gh_clean must repair a bowtie polygon and return a polygon, not a
    -- collection, or the typed column insert will fail.
    IF ST_GeometryType(core.gh_clean(
           ST_GeomFromText('POLYGON((0 0, 1 1, 1 0, 0 1, 0 0))', 4326))
       ) NOT IN ('ST_Polygon', 'ST_MultiPolygon') THEN
        RAISE EXCEPTION 'gh_clean did not return a polygon for a self-intersecting input';
    END IF;

    RAISE NOTICE 'All Ghana helper function tests passed.';
END
$$;

-- The metadata registry must exist and be queryable.
SELECT count(*) AS registered_datasets FROM meta.dataset;
SELECT count(*) AS serve_views FROM information_schema.views WHERE table_schema = 'serve';

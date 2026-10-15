"""Configuration tests.

These run without a database, without network access and without GDAL, so
they can gate every pull request cheaply. They check the things that are easy
to get wrong and annoying to discover later: a data source added without a
licence, or config/ghana.yml drifting away from the constants hardcoded in SQL.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def ghana():
    return yaml.safe_load((ROOT / "config" / "ghana.yml").read_text())


@pytest.fixture(scope="module")
def sources():
    return yaml.safe_load((ROOT / "config" / "sources.yml").read_text())["sources"]


def test_bbox_covers_ghana(ghana):
    b = ghana["bbox"]
    assert b["west"] < b["east"], "west must be less than east"
    assert b["south"] < b["north"], "south must be less than north"
    # Ghana spans roughly 3.3W to 1.2E and 4.5N to 11.2N. A bbox that does not
    # contain Accra and Bolgatanga is wrong.
    assert b["west"] <= -0.187 <= b["east"], "bbox must contain Accra"
    assert b["south"] <= 10.786 <= b["north"], "bbox must contain Bolgatanga"


def test_sixteen_regions(ghana):
    assert len(ghana["regions"]) == 16
    assert len(set(ghana["regions"])) == 16, "duplicate region name"
    # The six regions created in 2018-19. Their absence means someone pasted a
    # pre-2018 list.
    for new in ["Ahafo", "Bono East", "North East", "Oti", "Savannah", "Western North"]:
        assert new in ghana["regions"], f"{new} missing — this is a pre-2019 region list"


def test_admin_counts(ghana):
    """Ghana has 16 regions and 260 districts in the current configuration."""
    assert ghana["admin"]["expected_regions"] == 16
    assert ghana["admin"]["expected_districts"] == 260


def test_reference_boundaries_present(ghana):
    """The committed boundaries are what makes the repository usable on clone."""
    import json

    reference = ROOT / "data" / "reference"
    counts = {"gha_admin0": 1, "gha_admin1": 16, "gha_admin2": 260}
    for layer, expected in counts.items():
        path = reference / f"{layer}.geojson"
        assert path.exists(), f"missing {path}"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data["features"]) == expected, \
            f"{layer}: {len(data['features'])} features, expected {expected}"


def test_district_pcodes_nest_in_regions():
    """P-codes carry the hierarchy; a mismatch breaks every downstream join."""
    import json

    reference = ROOT / "data" / "reference"
    regions = {f["properties"]["adm1_pcode"]
               for f in json.loads((reference / "gha_admin1.geojson").read_text())["features"]}
    districts = json.loads((reference / "gha_admin2.geojson").read_text())["features"]

    assert all(len(p) == 4 and p.startswith("GH") for p in regions)
    orphans = [d["properties"]["adm2_pcode"] for d in districts
               if d["properties"]["adm2_pcode"][:4] not in regions]
    assert not orphans, f"districts with no parent region: {orphans[:5]}"


def test_crs_choices(ghana):
    assert ghana["crs"]["storage"] == 4326, "storage CRS must be lon/lat"
    assert ghana["crs"]["metric"] in (32630, 32631, 2137), "metric CRS must be projected"


def test_cities_inside_bbox(ghana):
    b = ghana["bbox"]
    for name, c in ghana["cities"].items():
        assert b["west"] <= c["lon"] <= b["east"], f"{name} longitude outside bbox"
        assert b["south"] <= c["lat"] <= b["north"], f"{name} latitude outside bbox"


def test_every_source_has_a_licence(sources):
    """The gate that stops undocumented data entering the stack."""
    for s in sources:
        assert s.get("licence"), f"{s['id']} has no licence"
        assert s.get("attribution"), f"{s['id']} has no attribution string"
        assert s.get("theme"), f"{s['id']} has no theme"
        assert s.get("status") in {"ready", "planned", "needs_agreement", "superseded"}, \
            f"{s['id']} has an invalid status"


def test_source_ids_unique(sources):
    ids = [s["id"] for s in sources]
    assert len(ids) == len(set(ids)), "duplicate source id"


def test_sql_constants_match_config(ghana):
    """config/ghana.yml and the SQL helpers must agree.

    core.gh_bbox() and core.gh_metric_srid() are hardcoded in SQL because a
    function has to be IMMUTABLE to be useful in an index. That duplication is
    deliberate, so this test exists to stop it drifting.
    """
    sql = (ROOT / "db" / "migrations" / "003_ghana_functions.sql").read_text()

    # Compare numerically. YAML parses -3.30 as -3.3, so a string comparison
    # against the SQL literal would fail on formatting alone.
    match = re.search(
        r"ST_MakeEnvelope\(\s*(-?[\d.]+),\s*(-?[\d.]+),\s*(-?[\d.]+),\s*(-?[\d.]+),\s*4326\s*\)",
        sql,
    )
    assert match, "core.gh_bbox() does not contain a recognisable ST_MakeEnvelope call"

    b = ghana["bbox"]
    expected = (b["west"], b["south"], b["east"], b["north"])
    found = tuple(float(g) for g in match.groups())
    assert found == expected, (
        f"core.gh_bbox() is {found} but config/ghana.yml says {expected}"
    )

    assert f"SELECT {ghana['crs']['metric']};" in sql, \
        "core.gh_metric_srid() does not match config/ghana.yml"


def test_skill_references_exist():
    """SKILL.md points at reference files; broken links make the skill useless."""
    skill_dir = ROOT / "skills" / "ghana-geosql"
    skill = (skill_dir / "SKILL.md").read_text()
    for name in ["postgis.md", "duckdb.md", "data-catalog.md", "crs.md", "map-styling.md"]:
        assert name in skill, f"SKILL.md does not mention {name}"
        assert (skill_dir / "references" / name).exists(), f"missing references/{name}"

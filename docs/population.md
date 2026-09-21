# Population: a worked example

Population is the layer that makes every other layer answerable. A flood map
says how much ground is low; a flood map with population says how many people
live on it. This walks the whole thing through, from an empty database to
numbers you can defend.

Allow about forty minutes, most of it waiting for downloads.

---

## What you get

| Table | Holds |
| --- | --- |
| `analysis.population_district` | Population, density, share of the national total, rank nationally and within the region |
| `analysis.population_region` | Regional totals, and how unevenly each region's people are spread |
| `analysis.population_access` | People within 2 km, 5 km and beyond 10 km of a health facility |
| `analysis.population_flood_exposure` | People living on flood-prone ground |
| `analysis.population_heat` | Mean surface temperature per district and its excess over the regional norm |

---

## Step 1 — the population raster

```bash
python pipelines/04_fetch_gee.py --show worldpop_population
python pipelines/04_fetch_gee.py worldpop_population
```

WorldPop at 100 m, clipped to Ghana. The first command prints the collection
id, licence and caveats before anything downloads.

Earth Engine needs a project once:

```bash
earthengine authenticate
echo "GEE_PROJECT=your-project-id" >> .env
```

## Step 2 — summarise it onto districts

```bash
python pipelines/05_zonal_stats.py data/raw/worldpop_population_ghana.tif \
    --zones district --stat sum --column population --load
```

This is zonal statistics: the pixels inside each district, summed, attached to
the district. It writes `data/exports/…_district_sum.csv` and, with `--load`,
`core.admin_district.population`.

**Check the total before going further.** The step prints it:

```
total   30,832,019
```

Ghana's 2021 census counted about 30.8 million. Landing near that means the
sum worked. An order of magnitude out means it did not — usually a raster
fetched for one city and summed as though it were national.

## Step 3 — run the analyses

```bash
python pipelines/30_run_analysis.py --only 05_population
```

Or `make analysis` for everything. The file checks its own output and prints a
regional table at the end:

```
region_name     districts   population   people_per_km2   pct_of_national
Greater Accra          29    5,446,237          1,678.4             17.66
Ashanti                43    5,440,463            223.2             17.64
...
```

Greater Accra and Ashanti each hold roughly a sixth of Ghana's people. Their
densities differ by a factor of seven, which is the entire story of the two
regions in one column.

---

## What this makes answerable

### Where people are, rather than where districts are

```sql
SELECT district_name, region_name,
       population, people_per_km2, pct_of_national
FROM analysis.population_district
ORDER BY people_per_km2 DESC
LIMIT 15;
```

The top of that list is Accra's sub-metros. Ranking by `population` instead
gives a different list, because a large sparse district can hold more people
than a crowded small one. Both are true; they answer different questions.

### Who is far from care, not how many buildings are

```sql
SELECT district_name, region_name,
       population,
       people_beyond_10km,
       pct_within_5km
FROM analysis.population_access
WHERE people_beyond_10km > 5000
ORDER BY people_beyond_10km DESC;
```

`01_accessibility.sql` counts buildings within 5 km of a clinic. This converts
that to people, by apportioning each district's population across its
buildings. The assumption — that people are spread evenly across buildings —
is wrong in detail and close enough at district scale. It is stated in the SQL
rather than buried.

### Who lives on ground that has flooded

```sql
SELECT district_name, region_name,
       population, people_exposed, people_under_2m, pct_exposed
FROM analysis.population_flood_exposure
WHERE people_exposed > 1000
ORDER BY people_exposed DESC;
```

Needs `02_flood_exposure.sql` first. Remember what that layer is: observed
historical surface water plus low terrain, with no return period and no depth.
"People living on ground that has been under water" is a defensible sentence.
"People at risk of flooding" is not.

### Urban heat, and who is in it

Two more fetches:

```bash
python pipelines/04_fetch_gee.py landsat_lst --start 2024-11-01 --end 2025-03-31

python pipelines/05_zonal_stats.py data/raw/landsat_lst_ghana.tif \
    --zones district --stat mean --column lst_c \
    --scale 0.00341802 --offset -124.15 --load
```

The scale and offset convert Landsat Collection 2's `ST_B10` from its stored
integer to Celsius in one pass. The date range is the dry season deliberately:
a thermal composite built through the rains is mostly cloud, and cloud reads
tens of degrees colder than the ground beneath it.

```sql
SELECT district_name, region_name,
       lst_c, region_mean_c, excess_c,
       population, people_per_km2
FROM analysis.population_heat
WHERE excess_c > 1.5
ORDER BY excess_c DESC;
```

`excess_c` compares each district to the mean of its own region, not to the
country. Ghana's north is hotter than its south for reasons that have nothing
to do with urban form, and a national comparison would just rediscover
latitude. A district running 2 °C above its neighbours is telling you
something about its surfaces.

Cross that against density and you have the heat exposure analysis: hot
districts that are also crowded, ranked by how many people are in them.

---

## The same machine, different inputs

Every one of those is the same operation. `05_zonal_stats.py` does not know
what it is summarising:

| Question | Command |
| --- | --- |
| Population per district | `--stat sum --column population` |
| Mean temperature per district | `--stat mean --column lst_c --scale 0.00341802 --offset -124.15` |
| Built-up area per district | `--stat sum --column built_m2` |
| Tree cover per district | `--stat mean --column treecover_pct` |
| Rainfall per catchment | `--zones data/raw/hydrosheds_basins_ghana.geojson --stat mean` |

That last one is worth noticing. `--zones` takes any vector file, so rainfall
can be summarised onto catchments rather than districts — which is the right
unit for water, since rivers do not respect administrative boundaries and a
flood reported per district hides where the water came from.

```bash
python pipelines/04_fetch_gee.py hydrosheds_basins
python pipelines/04_fetch_gee.py chirps_rainfall --start 2024-01-01 --end 2024-12-31
python pipelines/05_zonal_stats.py data/raw/chirps_rainfall_ghana.tif \
    --zones data/raw/hydrosheds_basins_ghana.geojson --stat mean --column rain_mm
```

---

## Seeing it

With the stack running, the analysis tables are served as vector tiles and
appear in the viewer's Layers tab.

Without a database, the CSV from step 2 is the route: it is keyed on p-code,
so it joins to the boundaries the viewer already has.

```sql
SELECT d.adm2_name, d.adm1_name, p.population, d.geom
FROM ghana.district d
JOIN read_csv_auto('data/exports/worldpop_population_ghana_district_sum.csv') p
  ON p.adm2_pcode = d.adm2_pcode
ORDER BY p.population DESC;
```

Then **Show on map**, and in the **Style** tab graduate by `population` and
switch to 3D. Districts raised and coloured by how many people live in them.

---

## What to say about these numbers

WorldPop is modelled, not counted. Census totals are distributed across a grid
using settlement pattern, land cover and roads.

That distinction survives aggregation badly. Summed to a district these
figures are defensible and close to the census they were built from. Read off
a single 100 m cell they are an estimate of where a model puts people, and
must never be presented as a headcount.

Where the Ghana Statistical Service publishes a figure for the same unit, the
GSS figure wins. This is what to use where they have not.

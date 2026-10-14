# Earth observation catalogue

`config/catalog.yml` is the single list of Earth observation datasets. Two
things read it and neither keeps its own copy, so they cannot disagree:

| Consumer | Uses |
| --- | --- |
| The viewer's **Data** tab | `browser` blocks - layers that load with no account |
| `pipelines/04_fetch_gee.py` | `gee` blocks - Earth Engine exports clipped to Ghana |

Eighteen datasets: seven load in the browser, eleven come through the pipeline.

## In the browser

Seven layers stream from NASA's GIBS, which serves keyless WMTS with CORS.
Open **Data**, search, press **Load**.

| Dataset | Resolution | Cadence |
| --- | --- | --- |
| MODIS true colour | 250 m | daily |
| VIIRS true colour | 375 m | daily |
| Vegetation index | 250 m | 16 days |
| Rainfall rate | 10 km | 30 minutes |
| Land surface temperature | 1 km | daily |
| Active fire detections | 1 km | daily |
| Night lights | 500 m | daily |

The date box applies to every temporal layer at once and defaults to three
days ago, because the latest pass is often not published yet. Ghana's rainy
season is also its cloudy season: if a day looks empty over the south between
April and October, step back two or three.

Loaded layers appear in the **Style** tab like anything else, so opacity and
removal work the same way.

## Through the pipeline

Everything above 500 m resolution, and everything needing a real composite,
runs through Earth Engine.

### Once

```bash
pip install earthengine-api
earthengine authenticate
echo "GEE_PROJECT=your-project-id" >> .env
```

The project needs the Earth Engine API enabled in the Google Cloud console.
The project id is read from `.env` from then on, so it is never typed again.

### Then

```bash
python pipelines/04_fetch_gee.py --list
python pipelines/04_fetch_gee.py --show esa_worldcover
python pipelines/04_fetch_gee.py esa_worldcover
python pipelines/04_fetch_gee.py chirps_rainfall --start 2024-01-01 --end 2024-12-31
python pipelines/04_fetch_gee.py sentinel2_l2a --start 2024-11-01 --end 2025-02-28 --city accra
```

The collection id, bands, reducer and export scale all come from the
catalogue. Sentinel-2 and Landsat are cloud-masked before compositing, and a
date range that matches nothing stops with that as the reason rather than
producing an empty file.

Small areas download straight to `data/raw/`. A national export at 10 m is far
past Earth Engine's direct-download limit, so it is routed to Drive and the
step says so up front rather than failing twenty minutes in.

### Available through Earth Engine

| Dataset | Collection | Resolution |
| --- | --- | --- |
| Sentinel-2 surface reflectance | `COPERNICUS/S2_SR_HARMONIZED` | 10 m |
| ESA WorldCover | `ESA/WorldCover/v200` | 10 m |
| Dynamic World | `GOOGLE/DYNAMICWORLD/V1` | 10 m |
| Tree cover and forest loss | `UMD/hansen/global_forest_change_2023_v1_11` | 30 m |
| Copernicus DEM GLO-30 | `COPERNICUS/DEM/GLO30` | 30 m |
| Surface water occurrence | `JRC/GSW1_4/GlobalSurfaceWater` | 30 m |
| Burned area | `MODIS/061/MCD64A1` | 500 m |
| Night lights, annual | `NOAA/VIIRS/DNB/ANNUAL_V22` | 500 m |
| Population | `WorldPop/GP/100m/pop` | 100 m |
| Built-up surface | `JRC/GHSL/P2023A/GHS_BUILT_S` | 100 m |
| CHIRPS rainfall | `UCSB-CHG/CHIRPS/DAILY` | 5 km |

## Adding a dataset

Add an entry to `config/catalog.yml`. A `browser` block makes it loadable in
the viewer; a `gee` block makes it fetchable by the pipeline; both is fine.
`scripts/build_web.py` recompiles the viewer's copy on every deployment, so
nothing else needs touching.

Every entry must carry a licence, an attribution string and a `notes` field.
The notes are not decoration - they say what the dataset does not tell you,
and they are shown to the reader beside the layer. A tree cover layer that
counts cocoa shade and oil palm as forest needs to say so in Ghana, where the
difference between forest and farm is the entire question.

# Map Styling — Ghana GeoStack

Adapted from the GeoSQL styling reference, with the choices that matter for
Ghanaian data called out.

## Pick the layer for the question

| Question | Layer | Avoid |
| --- | --- | --- |
| Where are things? | Point | Heatmap — it hides position |
| How dense? | H3 hexes, or tuned points | District choropleth of a raw count |
| Comparison across regions | Polygon choropleth of a **rate** | Choropleth of a count |
| Vertical magnitude | 3D polygon height | Colour alone |
| Building form | 3D extrusion by `height_m` | Flat fill, which loses the skyline |
| Flows between places | Arc | Line, which implies a route |
| Movement along a route | Line or Trip | Arc |

## The Ghana-specific trap: district choropleths lie

District areas in Ghana vary by more than two orders of magnitude. Accra
Metropolitan is around 140 km²; districts in the Northern and Savannah regions
run past 5,000 km². A choropleth gives the large sparse district enormous
visual weight and the dense urban one almost none, so a map of "where the
buildings are" comes out looking like a map of where they are not.

Two fixes, both better than the choropleth:

- **H3 hexes** (`h3.building_density_r7`, `serve.building_density`). Equal
  area, so visual weight matches magnitude.
- **Rates, not counts.** `pct_exposed`, not `exposed_buildings`. Per capita,
  per km², per building. A count choropleth is almost always a population map
  wearing a disguise.

## Density defaults

The instinct to clamp row counts and enlarge symbols is wrong. Invert it.

- Points: radius 2–4 px, opacity 0.6–0.8, 50k–1M rows is fine
- Lines and roads: 0.5–1.5 px; emphasis lines 2–4 px
- Polygon borders: 0.5–1 px hairline, lower opacity than the fill
- Arcs: 1–2 px, opacity 0.3–0.5 when they overlap
- H3: resolution 5 national, 7 regional, 9 urban

Do not `LIMIT` below 50k unless cost forces it. Ghana's full building set is
millions of rows and modern renderers handle it.

## Encode with more than one channel

Colour for the primary variable, radius or stroke width for magnitude, height
for a second numeric dimension. Opacity is for overlap, not for data.

Do not show the same thing twice: a tuned point layer already shows density,
so skip the heatmap on top; if the fill encodes a value, skip the outline
colour encoding the same value.

## Palettes

- **Sequential** (Viridis, Sunset, YlOrRd) for magnitude
- **Diverging** (RdBu) only where there is a real midpoint — change since
  2010, above or below the national average
- **Qualitative** (Set2, Tableau10) for up to 8 categories
- **Never rainbow or jet.** It invents boundaries that are not in the data

Ghana-specific: avoid red-green as the only distinction on anything about
agriculture or vegetation, both for colour-vision reasons and because green
already reads as vegetation on a land-cover map.

## 3D extrusion

The viewer's **Map → Dimension** switch extrudes every layer that carries a
magnitude. Buildings rise by `height_m` in real metres; districts and the
analysis layers rise by the value being mapped.

Use it when the question is about magnitude and the reader needs to compare
across the map at a glance — height is read faster and more accurately than
colour. Two cautions:

- **Extrude the finding, not its inverse.** `serve.access_by_district` rises by
  the shortfall, so the tall blocks are the districts furthest from care.
  Extruding the good news would bury the point.
- **Tilt the camera.** A flat view over an extruded map shows only the tops of
  the blocks and is strictly worse than the 2D version. The viewer tilts
  automatically; a Dekart or kepler.gl scene needs it set by hand.

## Basemap

Dark for point clouds and flows. Light for choropleths and anything going to
print. Ghana's north is sparse — a dark basemap makes a national point map of
facilities look like a coastal-only dataset, so check the render at national
zoom before choosing.

## Layer order

Bottom to top: basemap, polygon fills, lines, points, labels. Selected
features always on top.

## Set the view where the insight is

Lock the initial view to where the thing you are showing is visible. A
national extent for an Accra-scale insight is a wasted map.

Useful views:

| Extent | Centre | Zoom |
| --- | --- | --- |
| Ghana | −1.02, 7.95 | 6.4 |
| Greater Accra | −0.19, 5.60 | 10.5 |
| Kumasi | −1.62, 6.70 | 11 |
| Tamale | −0.84, 9.40 | 11 |
| Northern belt | −1.00, 9.80 | 7.5 |

## Every map carries its sources

Non-negotiable, and not only for legal reasons — a map without provenance
cannot be checked.

- Title saying what is shown and for when
- Attribution from `meta.dataset.attribution` for every layer used
- The date the data was extracted
- For derived layers, what the number means: "buildings within 250 m of a
  watercourse and under 5 m above its bed", not "flood risk"

## Look at the render before describing it

Do not narrate visual insight from row counts. If you have not seen the
rendered image, report what the numbers show and say the map has not been
inspected. A snapshot showing only basemap means the layer binding is wrong —
check the geometry column name, the data id and the column types before
blaming the renderer.

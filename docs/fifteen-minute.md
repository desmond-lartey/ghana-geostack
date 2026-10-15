# The 15-minute profile

**Analyze → Statistics → 15-Minute Profile**, then click anywhere in Ghana.
It walks the real street network out from that point at 5, 10 and 15 minutes,
counts what is reachable in each band, and says what the place is short of.

It is a diagnosis rather than a map. Drawing the catchments is the easy part.
The question worth answering is whether someone living at that point can
reach what a day needs, and the six axes are an attempt at that question.

---

## What it does, in order

1. **Fetches the walking network** around the point from Overpass — about a
   square kilometre and a half of footways, paths and streets.
2. **Builds a graph** from the way node lists: every consecutive pair of
   nodes is an undirected edge weighted by its length in metres. Undirected
   because on foot every street is two-way, whatever the tagging says about
   cars. Motorways, trunk roads and anything tagged `foot=no` or
   `access=private` are left out.
3. **Walks it** with Dijkstra from the nearest node, in metres, to the
   15-minute budget.
4. **Draws the catchments** as the land those streets serve.
5. **Fetches what is there** — shops, schools, clinics, stops, parks — and
   counts what falls inside each band.
6. **Scores six axes** and writes a reading.

Nothing is pre-computed and nothing is uploaded. That is the point: a
15-minute catchment is only interesting where someone points, and nobody can
pre-compute every point in Ghana.

---

## Walking speed, and why the catchment is lumpy

**80 metres a minute — 4.8 km/h.** The figure the 15-minute-city literature
uses. So 5 minutes is 400 m of walking, 10 is 800 m and 15 is 1,200 m —
*along the streets*, which is the whole distinction. On a regular grid the
area you can reach in 1,200 m of walking is about half the area of a circle
of 1,200 m radius; in a place with few through-routes it is far less. A
circular buffer drawn at 1,200 m is not a catchment and overstates reach
everywhere.

The catchment is the land within about 67 m of a reachable street, worked out
on a 45 m grid and merged into rectangles. Two reasons for cells rather than
a smooth hull:

- **A hull bridges streets that do not connect.** Two parallel roads with no
  crossing between them would be joined into one blob, and that is the single
  thing a catchment must never do.
- **The blocky edge is honest.** It is the resolution of the claim, not a
  smoothed guess about it.

---

## The seven functions

Counted separately, because "sixty places within a walk" means something
different when fifty-five of them are churches.

| Function | What counts |
| --- | --- |
| Daily Retail & Local Services | Any shop, plus markets, banks, post offices, fuel, cafés and eating places |
| Education | Schools, kindergartens, colleges, universities, libraries |
| Healthcare | Hospitals, clinics, doctors, pharmacies, dentists, anything tagged `healthcare` |
| Green & Recreation | Parks, gardens, playgrounds, pitches, reserves |
| Public Transport Access | Bus stops and stations, taxi ranks, rail halts, ferry terminals |
| Culture, Sport & Community | Places of worship, community centres, theatres, cinemas, museums, sports centres |
| Employment & Economic | Offices, crafts, industrial and commercial land, public institutions |

The grouping is a judgement and not a standard, and it is the judgement that
decides what the radar says — a pharmacy counted as retail rather than
healthcare changes whether a neighbourhood looks served. The full tag list is
in `URBAN_FUNCTIONS` in `web/index.html`, written out so it can be argued
with and changed.

**Essentials** are retail, education, healthcare and transport.

---

## The six axes

Each is 0–100 against a **stated reference**, never against "good". A score
of 70 means seventy per cent of the reference, and the reference is written
on the panel beside it.

| Axis | What it is | Reference |
| --- | --- | --- |
| **Coverage** | Functions reachable at all in 15 minutes | 7 of 7 |
| **Density** | Places per km² of the 15-minute catchment | 150/km², a busy urban quarter |
| **Diversity** | Shannon entropy across the functions | its maximum for seven functions |
| **Essentials** | Essential functions reachable within **10** minutes | 4 of 4 |
| **Choice** | Of the functions present, the share with three or more options | all of them |
| **Network** | Reachable street length per km² of catchment | 20 km/km², a fine-grained grid |

Two of these deserve a note.

**Diversity** is the entropy measure from the hotspots notebook. A place with
sixty shops and nothing else scores zero however many places it has; a place
with eight of each function scores near 100. It is the corrective to Density,
which cannot tell a market from a mixed neighbourhood.

**Choice** is the distinction the routing notebook draws with pandana's
`nearest_pois`: the time to the nearest shop says whether a shop exists, and
the time to the fifth says whether there is a *choice* of shop. One clinic is
a clinic until it closes. The threshold of three is arbitrary and is stated.

The density and network references are set against a well-served
neighbourhood in Accra or Kumasi rather than against Paris. A scale nothing
in Ghana can reach measures nothing.

---

## The radar lens

**Analyze → Statistics → Radar Lens**, or the button on the profile panel.

The same six axes as a chart you drag across the map. The disc under it is
highlighted and the spokes recompute from whatever is inside it, live, as it
moves. Drag it from the centre of a town to its edge and watch Coverage
collapse.

The idea is VisQuill's data lens, and it is a better one than it first looks.
A choropleth makes you read a colour, find the legend, and convert back to a
number, and it can only carry one variable. A lens carries six as a shape,
and comparing two neighbourhoods is a drag rather than two maps side by side.

It reads from the network the last profile fetched, so it does not call
Overpass as it moves — and outside that area it says so rather than quietly
reporting counts cut off by the edge of the download. It will also read any
drawn layer's numeric columns, averaged inside the disc and scaled against
that column's own range, which is the only reference a column of unknown
units can have.

---

## The other three tools

In the same group, and from the same notebooks.

**Hot Spots** — DBSCAN over a point layer, in metres, then Shannon entropy
per cluster and the categories each cluster has more of than the layer as a
whole. The entropy says whether a cluster is a mixed quarter or a
specialised one; the categories say what it specialises in. Clustering is
done in metres and not degrees: `eps = 0.002` means nothing, `eps = 200 m`
means a two-minute walk.

**Intersection Density** — real intersections, where three or more street
ends meet, per km². Nodes that merely describe a curve and dead ends are not
intersections, and counting them is why a raw node count says nothing about
the street pattern. This is what osmnx's `consolidate_intersections` is for.

**Walking Times** — time on foot to the first, third and fifth nearest of
each function, which is pandana's `nearest_pois` with the choice-depth
distinction kept.

---

## What it cannot tell you

- **OpenStreetMap is uneven in Ghana.** Accra and Kumasi are well mapped;
  much of the north is not. An empty catchment in a district capital is more
  likely a gap in the map than a gap on the ground, and the tool says so when
  it finds no streets at all. It cannot say so when it finds some.
- **A door on the map is not an open door.** Nothing here knows opening
  hours, whether the clinic has a nurse, or whether the school takes girls.
- **Walking distance is not walkability.** The network does not know about
  gutters, lighting, flooding in September, or whether a woman would walk
  that road after dark. A high score means the distance is short.
- **The last leg is a straight line.** A place is attached to the nearest
  street node within 250 m, as pandana does it. Where that 250 m crosses a
  wall, the time is wrong.
- **Scores are not comparable across countries.** The references are set for
  Ghanaian cities on purpose.

---

## Checking it

`tests/fifteen.cjs` runs the whole chain against a fixture: a 13 × 13 grid of
streets 200 m apart with places at known distances. The grid makes the
answers knowable in advance — and the test that matters is that the
15-minute catchment comes out at about a quarter of the area of the
crow-fly circle of the same radius. A catchment near the full circle would
mean the tool had drawn a buffer and walked nothing.

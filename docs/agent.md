# The Ask tab, and what it can do

Ask used to write SQL and stop. You read it, pressed Run, and did the rest
yourself. It now operates the viewer: it moves the map, shows layers, queries
the database, draws the answer and colours it by the value.

The design is taken from GeoAgent, which does the same thing for QGIS. Every
action is declared once as a tool, with the metadata that decides how it is
treated, and the model is given that list and left to work.

---

## What it can do

| Tool | What it does |
| --- | --- |
| `get_map_state` | Where the map is: centre, zoom, visible area, projection |
| `list_layers` | Every layer, whether it is drawn, whether it needs a database |
| `list_tables` | The queryable tables and their columns |
| `fly_to` | Move to a longitude and latitude |
| `zoom_to_place` | Move to a named region or district, fitted to its real extent |
| `set_layer_visible` | Show or hide a layer |
| `run_sql` | Run a read-only query and return the rows |
| `show_result_on_map` | Draw the last result |
| `style_by_column` | Colour it by a numeric column, optionally in 3D |
| `search_earth_engine` | Search the catalogue by keyword, with bands and class lists |
| `add_earth_engine_layer` | Draw a dataset over Ghana, with its own colours and legend |
| `land_cover_areas` | Square kilometres of each class per region, for classified data |
| `summarise_earth_engine` | Reduce a continuous dataset onto regions or districts |

The reading tools come first deliberately. An agent that can see the map before
changing it makes far better decisions than one working blind, and the
difference shows immediately on a question like "what is the densest district
in the area I am looking at".

---

## Using it

Ask needs your own API key — **Map** tab, under the model settings. Without one
the tab falls back to the old behaviour: it asks the shared endpoint for a
query, or matches one of the built-in question patterns, and you run it
yourself. Nothing that worked before stopped working.

With a key, try:

- *Which five districts have the most people?*
- *Show me Ashanti and colour the districts by population*
- *What is the largest district by area in the Northern Region?*
- *Zoom to Tamale*
- *Fetch ESA WorldCover, add it to the map, and compute land cover area per region*

That last one is four tools in sequence: it searches the catalogue, draws the
layer with the producer's colours and a legend, counts pixels per class per
region on Google's machines, and queries the resulting table.

It reports each step as it goes — which tool, which turn — and the **Log** tab
keeps every call and its arguments.

The query it ran is left in the Query tab, visible and editable. That is
deliberate: an answer you cannot check is worth less than one you can.

---

## What stops it

**A turn limit.** Eight steps, then it stops and says so. A loop with tools and
no bound is a way to spend your money while you watch a spinner.

**Read-only SQL.** `run_sql` refuses anything that is not a `SELECT` or `WITH`,
by the same check the Query tab uses.

**A confirmation gate.** The three Earth Engine tools spend your own quota on
Google's machines, so each shows the tool and its arguments and waits for you.
The other ten are local and instant and run freely.

**The right tool for the kind of raster.** `land_cover_areas` refuses a
continuous dataset and `summarise_earth_engine` refuses a classified one, each
naming the other. The average of two class codes is not a number that means
anything, and an agent that produces one produces it confidently.

**Geometry is withheld from the model.** A query that selects `geom` keeps it
for the map, but the model is sent the row count and the attributes only.
Coordinates are megabytes and tell a language model nothing.

---

## Adding a tool

One entry in `AGENT_TOOLS` in `web/index.html`:

```js
  count_buildings: {
    category: "data",
    description: "How many buildings are in a named district. Say what the " +
                 "number does and does not include, because the model will " +
                 "repeat this description back to the person.",
    schema: {
      type: "object",
      properties: { district: { type: "string" } },
      required: ["district"]
    },
    run: async ({ district }) => { /* … */ }
  }
```

The same entry produces the schema sent to the model, the gate that asks before
running, and the row in the table above. Adding a capability is one declaration
rather than three that drift apart — which is the whole point of GeoAgent's
registry, and of the `ModuleSpec` registry in the Savana plugin. Two projects
arriving at the same shape is a good sign it is the right one.

Write the description for the model, not for a reference manual. It is the only
thing deciding whether the tool gets used correctly, and a vague one produces a
tool that is called at the wrong moment with the wrong arguments.

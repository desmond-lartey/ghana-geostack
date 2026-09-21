# Earth Engine in the browser

The viewer can search the whole Earth Engine catalogue — around eleven hundred
datasets — draw any of them over Ghana, and reduce them to a table you can
query and style alongside everything else on the page.

It runs against your own Earth Engine account. The site holds no credential of
its own, which is the only honest arrangement for a static page: a service
account key shipped to a browser is a key given away. The consequence is that
each person connects once with their own, and the quota and the terms of use
are theirs.

---

## What you need

Two things, and a project id alone is not enough.

| | What it is | Where it comes from |
| --- | --- | --- |
| **Cloud project id** | The project registered for Earth Engine | `code.earthengine.google.com`, or an existing project |
| **OAuth client id** | Permission for *this website* to sign you in | Google Cloud console → Credentials |

The second one catches people out. Earth Engine will not accept an anonymous
browser, and a project id is a name, not a credential. The OAuth client is what
says "this particular site may ask this particular person to sign in".

### Creating the OAuth client

1. Open the Google Cloud console for the project registered with Earth Engine.
2. **APIs & Services → Credentials → Create credentials → OAuth client ID**.
3. Application type: **Web application**.
4. Under **Authorised JavaScript origins**, add the address the viewer is
   served from, with no trailing slash:

   ```
   https://your-project.vercel.app
   http://localhost:8080
   ```

   Add the local one too if you run `make serve`. An origin that is not listed
   is refused, and the error Google returns says only `idpiframe_initialization_failed`,
   which is not a helpful sentence.
5. Copy the client id. It looks like
   `000000000000-abcdefg.apps.googleusercontent.com`.

Both values are kept in your browser's local storage. Nothing is sent anywhere
but Google, and the scope requested is `earthengine.readonly` — this page
cannot write to your assets or start exports.

---

## Using it

Open the **Data** tab. The Earth Engine panel sits above the curated
catalogue.

**Connect** once. After that the values are remembered and the button signs
you straight in.

**Search.** Type what you are after — `elevation`, `population`, `rainfall`,
`nightlights`. Results show the real Earth Engine id, the producer, the native
resolution and the date span. Datasets whose footprint covers Ghana are listed
first, and one that does not is marked, because a dataset of Canadian land
cover will draw an empty rectangle rather than an error.

**Open** a dataset and the form is already filled in:

- a date range, defaulting to the last year rather than the dataset's whole
  life — compositing twenty years to look at Ghana once is a long wait for a
  worse picture
- how to combine the images, defaulting to the median, which is the usual way
  to see through cloud
- bands, and a minimum, maximum and palette

The rendering is not guesswork where it does not have to be. Earth Engine
publishes a suggested visualisation for most collections, and the panel says
which of the two you are looking at.

**Add to map** clips the result to Ghana's boundary and draws it. Before
drawing, it counts the images in your date range and tells you if there are
none, because an empty composite draws as blank tiles and looks identical to a
layer that failed.

---

## The part that matters

A raster on the map is a picture. **Summarise by region** and **Summarise by
district** turn it into numbers.

That runs `reduceRegions` on Google's machines against the geoBoundaries
administrative units for Ghana, and brings back one row per unit. The result
lands in the browser database as `ghana.ee_<dataset>_<level>`, which means the
rest of the page already knows what to do with it:

```sql
SELECT t.adm1_name, t.mean, b.geom
FROM ghana.ee_worldpop_pop_region t
JOIN ghana.region b ON b.adm1_name = t.adm1_name
ORDER BY t.mean DESC;
```

Run that, press **Show on map**, then open the **Style** tab and graduate by
the value column. Districts coloured and raised by whatever you just
summarised.

The reducer follows your choice on the form: **sum** if you picked sum — which
is what population and rainfall want — and **mean** otherwise, which is what
temperature and tree cover want. Summing a temperature is meaningless, and the
form is where that choice belongs.

---

## Where this fits

There are now three routes to the same kind of answer, and they differ in
where the work happens.

| Route | Work happens | Good for |
| --- | --- | --- |
| Earth Engine panel | Google's machines, from the browser | Exploring, one-off questions, anything not yet in the pipeline |
| `04_fetch_gee.py` + `05_zonal_stats.py` | Your machine | Reproducible results, version control, the full-resolution raster on disk |
| Curated catalogue | NASA's tile servers | A quick keyless look with no account at all |

The panel is for finding out whether a dataset is worth the trouble. Once it
is, the pipeline is where it belongs, because a result you can re-run is worth
more than one you clicked.

---

## When it does not work

**"Sign-in failed"** — almost always the authorised JavaScript origins. The
address in the browser's URL bar must appear there exactly, including
`https://` and any port, and without a trailing slash.

**"Earth Engine refused the project"** — the project is not registered for
Earth Engine, or the Earth Engine API is not enabled on it.

**The layer draws nothing** — check the date range first. The panel reports
the image count before drawing, so a zero there is the answer. After that,
check the band: a band name that does not exist in the collection produces an
empty image rather than an error.

**Search says the index is missing** — the catalogue index is built at deploy
time by `scripts/build_ee_catalog.py`. If Google was unreachable during the
build it is skipped rather than failing the deployment, and the next deploy
will pick it up.

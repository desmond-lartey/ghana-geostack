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

**If you are using a deployment someone else runs:** your own Earth Engine
project, and nothing else. Press *Sign in with Google*, approve the access, and
you are in. The site carries its own sign-in registration; you do not register
anything.

The project is yours because Earth Engine runs the work against it — that is
whose quota is spent and whose terms apply. It is free for non-commercial use;
register one at `code.earthengine.google.com`.

**If you run the site yourself**, register one OAuth client for it, once. A
client id identifies the *application* to Google, not the person, so one serves
every visitor. It is public by design — it appears in the page source and in
every sign-in request — and is set at build time, not typed in by users.

### Registering the site's client

1. In the Google Cloud console, open the project you want the client to belong
   to. This need not be the project anyone runs analyses against.
2. **APIs & Services → Credentials → Create credentials → OAuth client ID**,
   type **Web application**.
3. Under **Authorised JavaScript origins**, add the address the viewer is
   served from, with no trailing slash:

   ```
   https://your-project.vercel.app
   http://localhost:8080
   ```

   Add the local one too if you run `make serve`. An origin that is not listed
   is refused, and Google's error says only `idpiframe_initialization_failed`.
4. Set the client id as `EE_CLIENT_ID` in the build — in Vercel, Settings →
   Environment Variables — and redeploy. The panel then asks visitors for
   nothing but their project.

   ```bash
   EE_CLIENT_ID=000000000000-abc.apps.googleusercontent.com make web
   ```

   The client **secret** is not used. The browser flow has no way to keep one,
   so there is nothing to protect and nothing to leak.

   An **API key** is not used either, and is not interchangeable with a client
   id. If one was created while setting this up, delete it: an unused key is
   something to lose rather than something to have.

5. **Decide who may sign in.** While the consent screen is in *Testing*, only
   the accounts listed under **Audience → Test users** can sign in; everyone
   else is refused with `access_denied`. To open it to the public, publish the
   consent screen. `earthengine.readonly` is a sensitive scope, so Google may
   require verification before an unlisted user can grant it — worth starting
   early if the site is meant for others.

If `EE_CLIENT_ID` is not set, the panel says so and offers a box to paste one
into, so a fresh clone still works for the person running it.

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

**Add to map** clips the result to whatever the clip is set to and draws it.
Before drawing, it counts the images in your date range and tells you if there
are none, because an empty composite draws as blank tiles and looks identical
to a layer that failed.

The boundary it clips to is this page's own — the same admin file the vector
tools cut with, sent to Earth Engine as coordinates. It used to be named to a
boundary asset on Google's side instead, which works only while the two agree
about spelling and about which regions exist. They need not: Ghana's six newest
regions were created in December 2018, so an older boundary set has no Oti to
match, and this project's own admin1 file spells one of the six "Northern
East". A name matching nothing gives an empty collection, whose geometry is
empty, and an image clipped to an empty geometry is a blank layer with no error
anywhere — which is why a region clip used to draw nothing until you set it
back to the whole country.

---

## Palettes and legends

A dataset comes with its own rendering, and which kind it is changes everything.

**A classified dataset** — land cover, burn severity, crop type — ships a class
table: this value is Tree cover and it is this green, because the producer said
so. There is no range or palette to choose, and choosing one would be wrong.
Class values are rarely consecutive (WorldCover runs 10, 20, 30 … 95), so they
are remapped to 0…n-1 before drawing, which is the only way a palette lines up
with them. A legend is drawn from the same table, because a class table makes
one possible and a colour ramp does not.

**A continuous dataset** — elevation, temperature, rainfall — needs a ramp, and
which ramp is a real choice. Ten are offered with a note on each:

| Palette | When |
| --- | --- |
| `viridis`, `magma`, `inferno` | Perceptually uniform. The safe default for a quantity |
| `turbo` | High contrast for spotting detail; not perceptually uniform |
| `terrain`, `elevation` | Land-shaped, for a DEM shown as a map |
| `water` | Pale to deep blue, for depth, occurrence and rainfall |
| `heat` | Cold to hot, where that reading is intended |
| `vegetation` | Red through green, as NDVI is conventionally shown |
| `greys` | No colour, for anything where colour would imply meaning |

Picking one fills the hex box, which stays the single source of truth, so a
named palette and a hand-typed one can never disagree about what is drawn. The
legend updates as you type.

---

## Land cover area by region

For a classified dataset the summarise buttons are replaced by **Land cover
area by region** and **by district**, because a mean or a sum of class codes is
meaningless — the average of Tree cover and Mangroves is nothing.

It counts pixels per class per zone and multiplies by pixel area, giving one
row per zone per class with `area_km2` and `pct_of_zone`, in a queryable table:

```sql
SELECT adm1_name, class_name, area_km2, pct_of_zone
FROM ghana.ee_v200_class_region
WHERE class_name = 'Tree cover'
ORDER BY area_km2 DESC;
```

Two things to know about the numbers. They are pixel counts times pixel area,
so a class thinner than one pixel is not represented at all — a hedgerow
between two fields is simply absent at 10 m. And the count is of the remapped
index, read back through the class table, so the class values in the output are
the producer's own.

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

The **Log** tab records every fetch, every layer drawn and every error, newest
first, with a button that copies the lot. It is the first place to look, and
the right thing to paste when reporting a problem: "it did not work" and a log
are very different messages.


**Sign-in sits on "Checking with Google" and never moves** — if this ever
returns after thirty seconds with "Google did not answer", nothing came back
from the sign-in call at all. Check that `accounts.google.com` is reachable and
that no privacy extension is blocking it.

If it hangs indefinitely on an older build, the cause was the client library
version. Up to 0.1.387 it signed users in through `gapi.auth2`, Google's
Sign-In JavaScript platform library, which has been shut down — the call never
calls back, so the panel waits for a popup that will never open. `EE_API` must
point at **0.1.388 or later**, the release that moved to Google Identity
Services.

**"Google hasn't verified this app"** — expected, not a fault, and the most
likely place to get stuck because the safe-looking button is the wrong one.
Google shows this to every test user of an app whose consent screen is still in
testing. Choose **Continue**, the plain link on the left; *Back to safety*
cancels the sign-in. It stops appearing once the consent screen is published
and verified.

**"Google needs you to approve access"** — expected, not a fault. A silent
sign-in only works for someone already signed in who has granted access before.
Otherwise the sign-in must be interactive, and browsers open a popup only from
a click, so the panel offers a button. If pressing it does nothing, allow
popups for this site.

**"Sign-in failed"** — almost always the authorised JavaScript origins. The
address in the browser's URL bar must appear there exactly, including
`https://` and any port, and without a trailing slash. If it says
`access_denied`, the consent screen is still in testing and you are not on its
test-user list.

**"The library's own request was refused by this site's content security
policy"**, with a host named — add that host to `connect-src` in `vercel.json`
and redeploy. Google's client libraries do not use a single address: besides
`earthengine.googleapis.com` they reach `content-*` and discovery hosts, which
is why the policy allows `https://*.googleapis.com` rather than a list that
only has to be incomplete once. A request the policy refuses never reaches the
network and the caller sees an empty response, which is how `Invalid JSON:`
with nothing after it is produced.

**"Could not start Earth Engine for &lt;project&gt;"** — the panel asks the
API directly and reports what it said, because the client library's own message
for this is `Invalid JSON:` followed by nothing. An empty body is what a browser
sees when a request is refused before it can be read, so the library names the
symptom and hides the cause.

The most common answer is that the **Earth Engine API is not enabled on that
particular project**. Enabling it on one project does nothing for another, and
the project in this box is the one that matters — not the one the OAuth client
lives in, and not whichever project the Cloud console happens to have selected.
The message links straight to the right page when that is the cause.

The other answers it distinguishes: a token that was never set, a project the
signed-in account cannot use, a project that does not exist, a rejected token,
and a request that never left the browser at all.

**The layer draws nothing** — the panel counts the images before drawing, and
when that count is zero it works out *why* rather than blaming the dates. Three
filters can empty a collection and only one of them is the date range, so each
is counted on its own and the message names the one responsible:

| What it says | What happened |
| --- | --- |
| The boundary came back empty | The clip's boundary returned no features, so there was no area to search. This is the boundary source, not the dataset |
| The boundary could not be read | The clip is a region or district whose shape is not loaded in this browser. Reload, or clip to the whole country |
| No images at all, before any filter | The id has changed, or the collection is empty for this account |
| None of them over Ghana | The dataset does not cover the area. Drawing it would give an empty rectangle |
| None in this date range | The dates. The message repeats the range the catalogue claims |
| None that are both | The passes over the area fall outside the range |

Two notes on dates. `filterDate`'s end is exclusive in Earth Engine, so a range
typed as the same day twice asks for nothing at all; the end you type is pushed
to the end of that day, because two dates mean both of them. And a band name
that does not exist in the collection produces an empty image rather than an
error, so check the band when the count is fine and the picture is not.

**"Could not load the Earth Engine library"** — the client library is pinned
to an exact version, because Google Hosted Libraries has no `latest` path. If
that version is ever withdrawn the URL returns 404 and the panel cannot start.
The error names the URL it tried; open it, and if it 404s, find a version that
does not and change `EE_API` in `web/index.html`.

**Search says the index is missing** — the catalogue index is built at deploy
time by `scripts/build_ee_catalog.py`. If Google was unreachable during the
build it is skipped rather than failing the deployment, and the next deploy
will pick it up.

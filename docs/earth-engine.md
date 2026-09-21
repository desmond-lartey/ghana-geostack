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

**"Earth Engine refused the project"** — the project is not registered for
Earth Engine, or the Earth Engine API is not enabled on it.

**The layer draws nothing** — check the date range first. The panel reports
the image count before drawing, so a zero there is the answer. After that,
check the band: a band name that does not exist in the collection produces an
empty image rather than an error.

**"Could not load the Earth Engine library"** — the client library is pinned
to an exact version, because Google Hosted Libraries has no `latest` path. If
that version is ever withdrawn the URL returns 404 and the panel cannot start.
The error names the URL it tried; open it, and if it 404s, find a version that
does not and change `EE_API` in `web/index.html`.

**Search says the index is missing** — the catalogue index is built at deploy
time by `scripts/build_ee_catalog.py`. If Google was unreachable during the
build it is skipped rather than failing the deployment, and the next deploy
will pick it up.

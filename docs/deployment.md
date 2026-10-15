# Deployment

Two deployments, independent of each other:

| Target | Serves | Trigger |
| --- | --- | --- |
| **Vercel** | The map viewer and the boundary files | Push to `main` |
| **GitHub Pages** | This documentation | Push to `main`, or manual |

Neither needs a running database. The viewer falls back to the committed
boundaries and disables the layers that require one.

---

## Vercel

### Connect the repository

1. In Vercel, choose **Add New → Project** and import the repository.
2. Leave the framework preset as **Other**. `vercel.json` supplies the build
   command and output directory, so the dashboard fields can stay empty.
3. Deploy.

The build runs `python3 scripts/build_web.py`, which assembles `public/` from
`web/index.html` and `data/reference/`. No dependencies are installed —
the script uses the Python standard library only, and `installCommand` is a
no-op — so a deployment takes a few seconds.

### Environment variables

Set these under **Settings → Environment Variables**. All are optional.

| Variable | Effect |
| --- | --- |
| `EE_CLIENT_ID` | The site's Google OAuth client id. Set it and visitors sign in to Earth Engine with one button; unset and the panel asks each of them for a client id. Public by design, not a secret — see [Earth Engine in the browser](earth-engine.md) |
| `TILES_URL` | Public pg_tileserv endpoint. Unset means a boundaries-only deployment |
| `SITE_URL` | Canonical URL, used to write `sitemap.xml` |
| `INCLUDE_EXPORTS` | Set to `0` to leave GeoParquet out of the deployment |
| `ANTHROPIC_API_KEY` | Enables the **Ask** tab, which turns a plain-English question into SQL |
| `ANTHROPIC_MODEL` | Overrides the model used for that translation |

### The Ask endpoint

`api/ask.js` deploys automatically as a Vercel serverless function. It takes a
question, returns SQL, and runs nothing: the query executes in the reader's
browser against data the browser already downloaded, after the reader has seen
the SQL.

Only the question travels. No row of the database is sent anywhere, which is
why the endpoint can be enabled on a public deployment without the data
leaving your control.

Without `ANTHROPIC_API_KEY` the endpoint reports that it is not configured and
the viewer falls back to a set of built-in question patterns, which cover the
common shapes — counts, rankings, districts within a named region — offline.

`scripts/build_web.py` rewrites the `gh:data-root` and `gh:tiles-url` meta tags
in the built page, so the same `web/index.html` works from the repository, from
Vercel, and from any other static host without editing.

### What gets deployed

```
public/
├── index.html                       the viewer
├── robots.txt
├── sitemap.xml                      when SITE_URL is set
└── data/
    ├── reference/*.geojson          boundaries, always
    └── exports/*.parquet            when present and under 40 MB
```

Exports above 40 MB are skipped. Static hosting is the wrong place for a
multi-gigabyte building table; publish those as release artefacts or from
object storage, and point `TILES_URL` at a tile server for the large layers.

`.vercelignore` keeps the pipeline, database and notebooks out of the
deployment, so only the few megabytes that matter are uploaded.

### Headers

`vercel.json` sets a content security policy allowing exactly what the viewer
needs: scripts and styles from jsDelivr, fonts from Google Fonts, basemap
tiles from CARTO, and `blob:` workers for DuckDB-WASM. Everything else is
refused.

Boundaries and exports are served with permissive CORS and
`Accept-Ranges: bytes`, so other sites and DuckDB-WASM can read them directly.

!!! note "DuckDB and SharedArrayBuffer"

    The deployment does not set `Cross-Origin-Opener-Policy` or
    `Cross-Origin-Embedder-Policy`, because doing so would block the CDN and
    font requests. DuckDB-WASM therefore selects its single-threaded bundle,
    which is slower on large queries but correct. To enable the multithreaded
    bundle, add both headers and self-host every asset.

### Serving vector tiles

A boundaries-only deployment needs no backend. To enable buildings, roads and
the analysis layers, run pg_tileserv somewhere reachable over HTTPS and set
`TILES_URL`.

Vercel cannot host pg_tileserv itself — it needs a persistent connection to
PostGIS. Run it on a VM, Fly.io, Railway or Cloud Run, alongside a managed
PostGIS instance such as Neon, Supabase or Crunchy Bridge.

Two things to configure on that host:

- **CORS** — allow the Vercel origin. The compose file sets
  `TS_CORSORIGINS` to `*` for development; narrow it in production.
- **Exposure** — pg_tileserv should connect as `ghana_read`, the read-only
  role created in `db/migrations/001_schemas.sql`, and should see only the
  `serve` schema.

### Preview deployments

Every pull request gets its own URL with the same build. Because the boundaries
are committed, a preview is fully functional without any backend, which makes
interface changes reviewable in the pull request itself.

---

## GitHub Pages

### Enable it once

**Settings → Pages → Build and deployment → Source: GitHub Actions.**

No branch to select and no `gh-pages` branch to maintain; the workflow
publishes the built site directly.

Do this before the first push. `actions/configure-pages` fails with
`Get Pages site failed` if Pages has not been enabled, and the run shows as a
red failure rather than a missing build.

### If no build appears

Check the **Actions** tab. Three things account for almost every case:

| Symptom | Cause | Fix |
| --- | --- | --- |
| No runs listed at all | The branch is not `main` or `master` | `git branch -M main && git push -u origin main` |
| Run fails at *Configure Pages* | Pages source not set to GitHub Actions | Set it, then re-run the job |
| Actions tab shows a prompt to enable | Actions disabled for the repository | Settings → Actions → General → Allow all actions |

The workflow also has `workflow_dispatch`, so it can always be started by hand:
**Actions → Documentation → Run workflow**.

### The workflow

`.github/workflows/docs.yml` runs on every push to `main` or `master`, and can
be run manually from the Actions tab. It:

1. installs Material for MkDocs from `requirements-docs.txt`
2. runs `scripts/sync_docs.py`
3. runs `mkdocs build --strict`, which fails on a broken internal link
4. uploads the result and deploys it to Pages

`--strict` is deliberate. A documentation site that silently accumulates dead
links is worse than one that refuses to build.

### Generated pages

Several pages have their canonical home elsewhere in the repository and are
copied into `docs/` at build time by `scripts/sync_docs.py`:

| Source | Page |
| --- | --- |
| `skills/ghana-geosql/SKILL.md` | Agent skill → Overview |
| `skills/ghana-geosql/references/*.md` | Agent skill → the rest, and Data |
| `CONTRIBUTING.md` | Project → Contributing |
| `AGENTS.md` | Project → Working with agents |
| `ROADMAP.md` | Project → Roadmap |
| `LICENSE-DATA.md` | Project → Data licensing |

The copies are gitignored, so each of these has exactly one source of truth.
Edit the original, never the page under `docs/`; every generated page carries
a comment saying where it came from.

### Working on the docs locally

```bash
pip install -r requirements-docs.txt
make docs-serve          # syncs, then serves on http://localhost:8000
```

`make docs-serve` runs `sync_docs.py` first. MkDocs is configured to watch
`skills/` as well as `docs/`, so editing a skill reference reloads the browser —
though the sync must be rerun to pick up a newly added file.

### Custom domain

Add a `CNAME` file containing the domain to `docs/`, set the domain under
**Settings → Pages**, and update `site_url` in `mkdocs.yml`. MkDocs copies
`CNAME` into the built site automatically.

---

## Checklist before going public

- [ ] Replace `desmond-lartey` throughout: `mkdocs.yml`, `vercel.json`, `README.md`,
      `.claude-plugin/*.json`, `scripts/sync_docs.py`
- [ ] Confirm the boundary licence on the
      [HDX dataset page](https://data.humdata.org/dataset/cod-ab-gha)
- [ ] Decide on a basemap. The default is none, which needs no third party.
      If you enable one, confirm its terms and consider self-hosting a style
      or a PMTiles archive for anything with real traffic
- [ ] Set `SITE_URL` in Vercel so the sitemap is written
- [ ] Narrow `TS_CORSORIGINS` from `*` to the deployed origin
- [ ] Run `make qc` and confirm it passes before publishing any export

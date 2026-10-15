/* The whole rainfall chain, with Earth Engine replaced by a recorder.
 *
 * This is the run a person asks for in one sentence: find a rainfall dataset,
 * draw it, reduce it onto regions, and query the result. Every link in it has
 * broken at least once, and always in the same way — a step that failed, or
 * produced something whose name the next step could not know, while reporting
 * success. So the assertions are about what each tool hands to the next.
 *
 *     node tests/ee_rainfall.cjs
 */
const fs = require("fs");
const http = require("http");
const path = require("path");

const ROOT = path.join(__dirname, "..", "public");
const PORT = Number(process.env.SMOKE_PORT || 8125);
const STUB = fs.readFileSync(path.join(__dirname, "smoke_viewer.cjs"), "utf8")
  .split("const STUB = `")[1].split("`;")[0];

function serve() {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const file = path.join(ROOT, req.url === "/" ? "index.html" : req.url.split("?")[0]);
      if (!fs.existsSync(file) || fs.statSync(file).isDirectory()) {
        res.writeHead(404); return res.end();
      }
      res.writeHead(200, { "content-type": file.endsWith(".html") ? "text/html"
        : file.endsWith(".json") ? "application/json" : "application/octet-stream" });
      fs.createReadStream(file).pipe(res);
    });
    server.listen(PORT, () => resolve(server));
  });
}

(async () => {
  if (!fs.existsSync(path.join(ROOT, "index.html"))) {
    console.error("public/index.html is missing. Run scripts/build_web.py first.");
    process.exit(1);
  }
  let chromium;
  try { ({ chromium } = require("playwright")); }
  catch {
    try { ({ chromium } = require("/home/claude/.npm-global/lib/node_modules/playwright")); }
    catch { console.log("playwright not installed, skipping the rainfall chain test"); return; }
  }

  const server = await serve();
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 820 } });
  await ctx.addInitScript(() => {
    try { localStorage.setItem("gh:safemode", "1"); sessionStorage.setItem("gh:recovered", "1"); }
    catch { /* storage blocked */ }
  });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));

  await page.route("**", (r) => {
    const u = r.request().url();
    if (/maplibre-gl@/.test(u)) {
      return r.fulfill({ status: 200, contentType: "application/javascript", body: STUB });
    }
    if (u.startsWith(`http://localhost:${PORT}`)) return r.continue();
    return r.abort();
  });
  await page.goto(`http://localhost:${PORT}/index.html`, { waitUntil: "load" });
  await page.waitForTimeout(1200);

  const out = await page.evaluate(async () => {
    // Earth Engine, as a recorder that answers a reduceRegions with sixteen
    // regions of rainfall. The names are the ones geoBoundaries uses, which is
    // the point of the unmatched-name check.
    const REGIONS = ["Ahafo", "Ashanti", "Bono", "Bono East", "Central", "Eastern",
      "Greater Accra", "North East", "Northern", "Oti", "Savannah", "Upper East",
      "Upper West", "Volta", "Western", "Western North"];
    const node = (kind, args) => {
      const target = {
        __kind: kind, __args: args,
        size: () => ({ evaluate: (cb) => cb(REGIONS.length, null) }),
        evaluate: (cb) => cb({
          features: REGIONS.map((n, i) => ({
            properties: { shapeName: n, sum: 900 + i * 55.5,
                          mean: 900 + i * 55.5 } }))
        }, null),
        getMap: (o, cb) => cb({ urlFormat: "https://tiles/{z}/{x}/{y}" }, null)
      };
      return new Proxy(target, {
        // `then` must stay undefined. Awaiting a value whose `then` is a
        // function makes JavaScript treat it as a promise and call it, so a
        // recorder that answers every property turns `await someEeObject` into
        // a wait for a resolve that never comes.
        get: (t, prop) => prop === "then" ? undefined
          : prop in t ? t[prop]
          : (typeof prop === "string" ? (...a) => node(prop, a) : undefined)
      });
    };
    window.ee = {
      ImageCollection: (id) => node("ImageCollection", [id]),
      Image: (id) => node("Image", [id]),
      FeatureCollection: (x) => node("FeatureCollection", [x]),
      Feature: (g) => node("Feature", [g]),
      Geometry: (g) => node("Geometry", [g]),
      Filter: { eq: (k, v) => ({ __filter: [k, v] }) },
      Date: (d) => ({ advance: () => ({ __date: d }) }),
      Reducer: { sum: () => ({}), mean: () => ({}), frequencyHistogram: () => ({}) }
    };

    const chirps = {
      id: "UCSB-CHG/CHIRPS/DAILY", title: "CHIRPS Daily: Precipitation",
      type: "image_collection", provider: "UCSB/CHG", resolution_m: 5566,
      start: "1981-01-01", end: "", covers_ghana: true,
      keywords: ["climate", "precipitation", "ucsb"],
      description: "Climate Hazards Group InfraRed Precipitation with Station "
        + "data is a quasi-global rainfall dataset spanning 50N-50S.",
      bands: [{ name: "precipitation" }]
    };

    // DuckDB cannot load in an offline test, and it is not what is being
    // tested: the summary writes a CSV and creates a table from it, so a fake
    // that records the CSV and answers the one name query is enough.
    const db = { files: {}, sql: [] };
    const fakeDuck = { registerFileText: async (n, csv) => { db.files[n] = csv; } };
    const fakeConn = {
      query: async (sql) => {
        db.sql.push(sql);
        const rows = /FROM ghana\.(region|district);/.test(sql)
          ? REGIONS.map((n) => ({ toJSON: () => ({ n }) }))
          : [];
        return { toArray: () => rows };
      }
    };

    const hook = window.__ghClip;
    hook.setReady(true);
    hook.catalog([chirps]);
    hook.setDb(fakeDuck, fakeConn);
    hook.setClip({ kind: "none", name: "", geometry: null });

    // Two versions of one product, so a name that matches both must not be
    // silently resolved to either.
    const wc100 = { id: "ESA/WorldCover/v100", title: "ESA WorldCover 10m v100",
      type: "image_collection", start: "2020-01-01", end: "2021-01-01",
      covers_ghana: true, keywords: ["landcover"], description: "Global land cover.",
      classes: { band: "Map", values: [10], colours: ["006400"], names: ["Tree cover"] },
      bands: [{ name: "Map" }] };
    const wc200 = { ...wc100, id: "ESA/WorldCover/v200",
      title: "ESA WorldCover 10m v200", start: "2021-01-01", end: "2022-01-01" };
    hook.catalog([chirps, wc100, wc200]);

    const steps = {};
    steps.search = await hook.tool("search_earth_engine", { query: "rainfall" });
    // A name, not an id: the tool should use it rather than send the model off
    // to search.
    steps.byName = await hook.tool("add_earth_engine_layer", {
      dataset_id: "CHIRPS", start: "2024-01-01", end: "2024-12-31",
      band: "precipitation", reducer: "sum" });
    // A name matching two datasets must come back as a choice, not a guess.
    steps.ambiguous = await hook.tool("add_earth_engine_layer", {
      dataset_id: "ESA WorldCover" });
    steps.draw = await hook.tool("add_earth_engine_layer", {
      dataset_id: chirps.id, start: "2024-01-01", end: "2024-12-31",
      band: "precipitation", reducer: "sum", palette: "water", min: 0, max: 2000 });
    // Annual rainfall: the year totalled at each pixel, then averaged over the
    // region. Two different reducers, and the tool used to expose only one.
    steps.summary = await hook.tool("summarise_earth_engine", {
      dataset_id: "CHIRPS", level: "region", band: "precipitation",
      statistic: "mean", over_time: "sum", start: "2024-01-01", end: "2024-12-31" });

    return { steps, sql: db.sql, csv: Object.values(db.files)[0],
             layers: window.__ghLayers.list().map((l) => l.label) };
  });

  await browser.close();
  server.close();

  const s = out.steps || {};
  const bad = [];
  if (!s.search || s.search.error) bad.push("search_earth_engine failed: " + (s.search?.error));
  // The word a person uses, not the word the producer uses.
  if (!Array.isArray(s.search) || !s.search.some((r) => r.id === "UCSB-CHG/CHIRPS/DAILY")) {
    bad.push("searching for rainfall did not find CHIRPS");
  }
  if (!s.draw || s.draw.error) bad.push("add_earth_engine_layer failed: " + (s.draw?.error));
  if (s.draw && s.draw.dataset_id !== "UCSB-CHG/CHIRPS/DAILY") {
    bad.push("the layer result does not name the dataset it drew");
  }
  if (s.byName?.dataset_id !== "UCSB-CHG/CHIRPS/DAILY") {
    bad.push("naming CHIRPS did not resolve to it: " + JSON.stringify(s.byName));
  }
  if (!s.ambiguous?.ambiguous) {
    bad.push("a name matching two datasets was not offered as a choice");
  }
  if (s.ambiguous?.ambiguous?.[0]?.id !== "ESA/WorldCover/v200") {
    bad.push("the newest match is not listed first: "
      + JSON.stringify(s.ambiguous?.ambiguous?.map((d) => d.id)));
  }
  if (s.summary && s.summary.dataset_id !== "UCSB-CHG/CHIRPS/DAILY") {
    bad.push("the summary does not name the dataset it used");
  }
  if (!out.layers?.length) bad.push("nothing was registered as a layer");
  if (!s.summary || s.summary.error) bad.push("summarise_earth_engine failed: " + (s.summary?.error));
  if (s.summary && !s.summary.table) bad.push("the summary did not return its table name");
  if (s.summary && s.summary.table !== "ghana.ee_daily_region") {
    bad.push("unexpected table name: " + s.summary.table);
  }
  if (s.summary && s.summary.zones !== 16) bad.push("expected 16 regions, got " + s.summary?.zones);
  if (s.summary && s.summary.statistic !== "mean") {
    bad.push("asked to average the pixels in each zone and got " + s.summary?.statistic);
  }
  if (s.summary && s.summary.over_time !== "sum") {
    bad.push("asked to total the images over time and got " + s.summary?.over_time);
  }
  // The table has to exist under the name handed back, or the next step fails.
  if (!out.sql?.some((q) => /CREATE OR REPLACE TABLE ghana\.ee_daily_region/.test(q))) {
    bad.push("no table was created under the name that was reported");
  }
  if (!/^adm1_name,mean\n/.test(out.csv || "")) {
    bad.push("the table was not written with the columns that were reported");
  }
  // Sixteen matching names in, none reported unmatched.
  if (s.summary?.unmatched_names) {
    bad.push("matching names were reported as unmatched: " + s.summary.unmatched_names);
  }
  if (s.summary && !/show_result_on_map/.test(s.summary.next || "")) {
    bad.push("the summary does not tell the model how to map it");
  }

  if (bad.length) {
    console.error("The rainfall chain breaks:");
    for (const line of bad) console.error("  " + line);
    console.error("  steps: " + JSON.stringify(out.steps));
    if (errors.length) console.error("  page errors: " + errors.slice(0, 3).join(" | "));
    process.exit(1);
  }
  console.log(`the rainfall chain runs — drew ${s.draw.drawn}, summarised `
    + `${s.summary.zones} regions into ${s.summary.table}`);
})();

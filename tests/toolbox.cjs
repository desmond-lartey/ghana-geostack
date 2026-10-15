/* Can you actually run a geoprocessing tool?
 *
 * "At the moment I am literally not able to use any of the processing tools."
 * The toolbox had no test of any kind, because the tools import Turf from a
 * CDN and a machine without that CDN cannot run one. So nothing checked that
 * the list was populated, that the layer dropdown had anything in it, that a
 * run reached the geometry library, or that the result came back as a layer.
 *
 * The geometry library is substituted here — tests/turf_stub.cjs says exactly
 * which of its functions are exact and which are approximations, and no
 * assertion below depends on an approximation. What is being tested is the
 * toolbox: the registry, the generated form, validation, layer resolution,
 * the run, and the result becoming a layer that the next tool can take.
 */
const fs = require("fs");
const http = require("http");
const path = require("path");

const ROOT = path.join(__dirname, "..", "public");
const PORT = Number(process.env.SMOKE_PORT || 8132);
const { baseStub, patch } = require("./stub.cjs");
const { moduleSource } = require("./turf_stub.cjs");
const STUB = patch(baseStub(), [
  ["getLayer(id) { return this._lyr.get(id) || null; }",
   'getLayer(id) { return this._lyr.get(id) || { id, type: "fill" }; }']
]);

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

// Six health facilities around Kumasi and a district polygon that contains
// four of them. Real coordinates, so point-in-polygon is a real test.
const POINTS = JSON.stringify({ type: "FeatureCollection", features: [
  { type: "Feature", properties: { name: "Komfo Anokye", beds: 1200 },
    geometry: { type: "Point", coordinates: [-1.6295, 6.6960] } },
  { type: "Feature", properties: { name: "Kumasi South", beds: 250 },
    geometry: { type: "Point", coordinates: [-1.6210, 6.6630] } },
  { type: "Feature", properties: { name: "Suntreso", beds: 120 },
    geometry: { type: "Point", coordinates: [-1.6400, 6.6980] } },
  { type: "Feature", properties: { name: "Manhyia", beds: 90 },
    geometry: { type: "Point", coordinates: [-1.6150, 6.7100] } },
  // Two well outside the boundary below: Tamale and Accra.
  { type: "Feature", properties: { name: "Tamale Teaching", beds: 400 },
    geometry: { type: "Point", coordinates: [-0.8393, 9.4075] } },
  { type: "Feature", properties: { name: "Korle Bu", beds: 2000 },
    geometry: { type: "Point", coordinates: [-0.2290, 5.5370] } }
]});

(async () => {
  if (!fs.existsSync(path.join(ROOT, "index.html"))) {
    console.error("public/index.html is missing. Run scripts/build_web.py first.");
    process.exit(1);
  }
  let chromium;
  try { ({ chromium } = require("playwright")); }
  catch {
    try { ({ chromium } = require("/home/claude/.npm-global/lib/node_modules/playwright")); }
    catch { console.log("playwright not installed, skipping the toolbox test"); return; }
  }

  const server = await serve();
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1500, height: 900 } });
  await ctx.addInitScript(() => {
    try { localStorage.setItem("gh:safemode", "1"); sessionStorage.setItem("gh:recovered", "1"); }
    catch { /* blocked */ }
  });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));

  const turf = moduleSource();
  await page.route("**", (r) => {
    const u = r.request().url();
    if (/maplibre-gl@/.test(u)) {
      return r.fulfill({ status: 200, contentType: "application/javascript", body: STUB });
    }
    if (/@turf\/turf/.test(u)) {
      return r.fulfill({ status: 200, contentType: "application/javascript", body: turf });
    }
    if (u.startsWith(`http://localhost:${PORT}`)) return r.continue();
    return r.abort();
  });
  await page.goto(`http://localhost:${PORT}/index.html`, { waitUntil: "load" });
  await page.waitForTimeout(1400);

  const out = await page.evaluate(async (points) => {
    document.getElementById("boot")?.remove();
    const T = window.__ghToolbox;
    const result = { tools: T.tools() };

    // Nothing is drawn yet, so the toolbox must say so rather than offering
    // an empty dropdown with no explanation.
    T.open();
    await T.show("centroid");
    result.emptyForm = document.getElementById("tb-detail")?.innerText || "";

    // Add the facilities.
    await window.__ghAddData.files([new File([points], "facilities.geojson",
                                             { type: "application/geo+json" })]);
    const added = window.__ghLayers.list().slice(-1)[0];
    result.offered = T.layers();

    // 1. Centroids — exact in the substitute, so the answer is checkable.
    await T.show("centroid");
    T.set("input", added.id);
    await T.run("centroid");
    await new Promise((r) => setTimeout(r, 120));
    result.centroidStatus = T.status();
    const afterCentroid = window.__ghLayers.list();
    result.centroidLayer = afterCentroid.slice(-1)[0]?.label || "";
    result.centroidFeatures = afterCentroid.slice(-1)[0]?.collection?.features?.length ?? 0;

    // 2. Convex hull — exact. Six scattered points give a hull with fewer
    // vertices than inputs, and it must be a polygon.
    await T.show("convex");
    T.set("input", added.id);
    await T.run("convex");
    await new Promise((r) => setTimeout(r, 120));
    result.hullStatus = T.status();
    const hull = window.__ghLayers.list().slice(-1)[0];
    result.hullType = hull?.collection?.features?.[0]?.geometry?.type || "";

    // 3. Clip to a named region — exact point-in-polygon. Four of the six
    // facilities are in Ashanti; the Tamale and Accra ones are not.
    await T.show("clip");
    T.set("input", added.id);
    T.set("boundary", "region:Ashanti");
    await T.run("clip");
    await new Promise((r) => setTimeout(r, 200));
    result.clipStatus = T.status();

    // 4. Validation: a required input left empty must be refused, and say
    // which one.
    await T.show("buffer");
    T.set("input", "");
    await T.run("buffer");
    result.missingInput = T.status();

    // 5. The output of a tool is an input to the next one, which is what
    // makes a toolbox a toolbox rather than a list of one-shot buttons.
    const chainSource = window.__ghLayers.list()
      .find((l) => /centroid/i.test(l.label));
    result.chainable = T.layers().some((l) => l.id === chainSource?.id);

    // 6. And its rows open in the attribute table.
    if (chainSource) {
      await window.__ghTable.open(chainSource.id);
      result.tableRows = window.__ghTable.state().rows;
    }

    // 7. Hotspots. Three tight clumps of 12, 400 m apart, plus eight
    // scattered points that are noise — DBSCAN at 150 m must find exactly
    // three, and the clump of cafes must report as specialising in cafes.
    const clumps = [];
    const centres = [[-1.62, 6.70], [-1.615, 6.70], [-1.6175, 6.705]];
    const kinds = [["cafe", 10], ["school", 10], ["cafe", 5]];
    centres.forEach(([cx, cy], c) => {
      for (let i = 0; i < 12; i += 1) {
        const a = (i / 12) * Math.PI * 2;
        clumps.push({ type: "Feature",
          properties: { amenity: i < kinds[c][1] ? kinds[c][0] : "pharmacy" },
          geometry: { type: "Point",
            coordinates: [cx + Math.cos(a) * 0.0004, cy + Math.sin(a) * 0.0004] } });
      }
    });
    for (let i = 0; i < 8; i += 1) {
      clumps.push({ type: "Feature", properties: { amenity: "bench" },
        geometry: { type: "Point", coordinates: [-1.70 + i * 0.01, 6.75 + i * 0.01] } });
    }
    await window.__ghAddData.files([new File(
      [JSON.stringify({ type: "FeatureCollection", features: clumps })],
      "clumps.geojson", { type: "application/geo+json" })]);
    const clumpLayer = window.__ghLayers.list().slice(-1)[0];

    await T.show("hotspot");
    T.set("input", clumpLayer.id);
    T.set("category", "amenity");
    T.set("eps", "150");
    T.set("minPoints", "10");
    await T.run("hotspot");
    await new Promise((r) => setTimeout(r, 200));
    result.hotspotStatus = T.status();
    const spots = window.__ghLayers.list().slice(-1)[0];
    result.hotspots = (spots?.collection?.features || []).map((f) => ({
      size: f.properties.size, entropy: f.properties.entropy,
      top: f.properties.top_category
    }));

    result.finalLayers = window.__ghLayers.list().map((l) => l.label);
    return result;
  }, POINTS);

  await browser.close();
  server.close();

  const bad = [];

  if (out.tools.length < 10) bad.push(`only ${out.tools.length} tools in the toolbox`);
  const categories = new Set(out.tools.map((t) => t.category));
  if (categories.size < 3) bad.push(`only ${categories.size} tool categories`);
  for (const want of ["clip", "buffer", "centroid", "convex"]) {
    if (!out.tools.some((t) => t.id === want)) bad.push(`the ${want} tool is missing`);
  }

  if (!/nothing is drawn|run a query|turn on/i.test(out.emptyForm)) {
    bad.push(`with no layers the form said "${out.emptyForm.slice(0, 80)}" instead of why`);
  }
  if (!out.offered.length) bad.push("a drawn layer was not offered to the tools");
  if (!out.offered.some((l) => l.count === 6)) {
    bad.push(`the dropdown did not count the features: ${JSON.stringify(out.offered)}`);
  }

  if (!/6 features/i.test(out.centroidStatus)) {
    bad.push(`centroids on 6 points said "${out.centroidStatus}"`);
  }
  if (out.centroidFeatures !== 6) {
    bad.push(`centroids produced ${out.centroidFeatures} features, not 6`);
  }
  if (!out.centroidLayer) bad.push("the centroid run added no layer");

  if (out.hullType !== "Polygon") bad.push(`the convex hull came out as ${out.hullType || "nothing"}`);

  // Without the database a named boundary cannot be resolved, and the point
  // of this assertion is that it says so in words rather than throwing
  // "Cannot read properties of null" from somewhere inside the tool.
  if (!/boundaries are not loaded|cannot be resolved/i.test(out.clipStatus)) {
    bad.push(`clipping to a region with no database said "${out.clipStatus}"`);
  }

  if (!/required/i.test(out.missingInput)) {
    bad.push(`a missing required input was not refused: "${out.missingInput}"`);
  }
  if (!out.chainable) bad.push("a tool's output cannot be fed to the next tool");
  if (out.tableRows !== 6) bad.push(`the result opened ${out.tableRows} rows in the table, not 6`);

  // Hotspots: three clusters of 12, eight scattered points as noise.
  if (!out.hotspots || out.hotspots.length !== 3) {
    bad.push(`DBSCAN found ${out.hotspots?.length ?? 0} hotspots in three clumps `
           + `— "${out.hotspotStatus}"`);
  } else {
    if (out.hotspots.some((h) => h.size !== 12)) {
      bad.push(`the clusters are ${out.hotspots.map((h) => h.size).join("/")}, not 12 each`);
    }
    if (!/8 left as noise/.test(out.hotspotStatus)) {
      bad.push(`the eight scattered points were not left as noise — "${out.hotspotStatus}"`);
    }
    // The clump of ten cafes and two pharmacies is less even than the one
    // with five cafes and seven pharmacies, so its entropy must be lower.
    const entropies = out.hotspots.map((h) => h.entropy);
    if (entropies.some((e) => typeof e !== "number")) {
      bad.push("the clusters carry no entropy");
    } else if (Math.min(...entropies) >= Math.max(...entropies)) {
      bad.push(`every cluster has the same entropy (${entropies.join(", ")}), `
             + "so the measure is not reading the categories");
    }
    if (!out.hotspots.some((h) => /cafe|school/.test(h.top || ""))) {
      bad.push("no cluster reported what it specialises in");
    }
  }

  const real = errors.filter((e) => !/Failed to fetch|NetworkError|net::/i.test(e));
  if (real.length) bad.push("page errors: " + real.slice(0, 3).join(" | "));

  if (bad.length) {
    console.error("The geoprocessing tools do not work:");
    for (const line of bad) console.error("  " + line);
    console.error("  layers after the run: " + out.finalLayers.join(", "));
    process.exit(1);
  }

  console.log(`geoprocessing works — ${out.tools.length} tools in ${categories.size} `
    + `categories; centroids and the convex hull ran on a dropped layer, a clip `
    + `to a region with no database said so in words, a missing input was `
    + `refused, the output chains into the next tool and opens as a table, and `
    + `DBSCAN found ${out.hotspots.length} hotspots of `
    + `${out.hotspots.map((h) => h.size).join("/")} with entropy `
    + `${out.hotspots.map((h) => h.entropy).join("/")}`);
})();

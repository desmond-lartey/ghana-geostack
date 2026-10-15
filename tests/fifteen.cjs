/* The 15-minute profile: does the walking actually walk?
 *
 * The map is stubbed and Overpass is answered from a fixture, so what is
 * under test is the part that matters and the part that could be quietly
 * wrong: the graph, Dijkstra, the catchments, the classification of OSM tags
 * into urban functions, and the six axes.
 *
 * The fixture is a grid of streets with a known shape, so the answers are
 * known in advance. A 300 m square block structure means the distance from
 * the centre to a corner three blocks out is 1800 m along the streets and
 * about 1270 m as the crow flies — and a catchment that reports the crow-fly
 * figure is a catchment that has not walked anything.
 */
const fs = require("fs");
const http = require("http");
const path = require("path");

const ROOT = path.join(__dirname, "..", "public");
const PORT = Number(process.env.SMOKE_PORT || 8133);
const { baseStub, patch } = require("./stub.cjs");
const STUB = patch(baseStub(), [
  ["getLayer(id) { return this._lyr.get(id) || null; }",
   'getLayer(id) { return this._lyr.get(id) || { id, type: "fill" }; }']
]);

/* A Manhattan grid centred on Kumasi: 13 × 13 nodes, 200 m apart, so the
   whole thing is 2.4 km across. Walking from the centre at 80 m/min:
   5 minutes reaches 400 m, which is two blocks; 15 minutes reaches 1200 m,
   which is six. Along the streets, not through the buildings. */
const LAT0 = 6.6885, LON0 = -1.6163;
const SPACING = 200;
const SIDE = 13;
const M_PER_LAT = 110574;
const M_PER_LON = 111320 * Math.cos(LAT0 * Math.PI / 180);

function gridPayload() {
  const elements = [];
  const id = (r, c) => 1000 + r * SIDE + c;
  for (let r = 0; r < SIDE; r += 1) {
    for (let c = 0; c < SIDE; c += 1) {
      const y = (r - (SIDE - 1) / 2) * SPACING;
      const x = (c - (SIDE - 1) / 2) * SPACING;
      elements.push({ type: "node", id: id(r, c),
        lat: LAT0 + y / M_PER_LAT, lon: LON0 + x / M_PER_LON });
    }
  }
  let wayId = 1;
  for (let r = 0; r < SIDE; r += 1) {
    elements.push({ type: "way", id: wayId++, tags: { highway: "residential" },
      nodes: Array.from({ length: SIDE }, (_, c) => id(r, c)) });
  }
  for (let c = 0; c < SIDE; c += 1) {
    elements.push({ type: "way", id: wayId++, tags: { highway: "residential" },
      nodes: Array.from({ length: SIDE }, (_, r) => id(r, c)) });
  }
  // A motorway through the middle, which must be ignored: walking along one
  // is not something a plan may assume.
  elements.push({ type: "way", id: wayId++, tags: { highway: "motorway" },
    nodes: [id(0, 0), id(SIDE - 1, SIDE - 1)] });
  return { elements };
}

/* Places at known distances from the centre, one per function so coverage
   and diversity have something definite to report. */
function placesPayload() {
  const at = (dx, dy, tags) => ({
    type: "node", id: Math.round(900000 + Math.random() * 1e5),
    lat: LAT0 + dy / M_PER_LAT, lon: LON0 + dx / M_PER_LON, tags
  });
  // On the streets, where OpenStreetMap actually puts them. A catchment
  // claims the land within about 67 m of a reachable street, so a shop
  // dropped in the middle of a block is correctly outside it — true of the
  // real thing, and a trap for a fixture.
  const elements = [];
  // Within 5 minutes, which is 400 m of walking: retail ×4, transport ×1.
  for (const [dx, dy] of [[200, 0], [400, 0], [0, 200], [0, -200]]) {
    elements.push(at(dx, dy, { shop: "convenience" }));
  }
  elements.push(at(-200, 0, { highway: "bus_stop" }));
  // Within 10 minutes, 800 m: education ×3, healthcare ×1.
  for (const [dx, dy] of [[600, 0], [0, 600], [-600, 0]]) {
    elements.push(at(dx, dy, { amenity: "school" }));
  }
  elements.push(at(0, -600, { amenity: "clinic" }));
  // Within 15 minutes, 1200 m: green ×2, at 1,000 m — which is 12.5 minutes,
  // so these must fall in the outer band and not the 10-minute one.
  elements.push(at(1000, 0, { leisure: "park" }));
  elements.push(at(0, 1000, { leisure: "playground" }));
  // Seven kilometres away: must not be counted at all.
  elements.push(at(5000, 5000, { amenity: "hospital" }));
  return { elements };
}

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
    catch { console.log("playwright not installed, skipping the 15-minute test"); return; }
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

  const net = JSON.stringify(gridPayload());
  const pois = JSON.stringify(placesPayload());

  await page.route("**", (r) => {
    const u = r.request().url();
    if (/maplibre-gl@/.test(u)) {
      return r.fulfill({ status: 200, contentType: "application/javascript", body: STUB });
    }
    // Overpass: the network query asks for ways by highway class, the places
    // query asks for shops and amenities. Told apart by what they ask for.
    if (/overpass/i.test(u)) {
      // A POST body is form-encoded, so "out body" arrives as "out+body".
      // Matching the raw string silently served the wrong fixture.
      const raw = r.request().postData() || u;
      const body = decodeURIComponent(raw.replace(/\+/g, " "));
      const network = /out body/.test(body) && !/\bshop\b/.test(body);
      return r.fulfill({ status: 200, contentType: "application/json",
                         body: network ? net : pois });
    }
    if (u.startsWith(`http://localhost:${PORT}`)) return r.continue();
    return r.abort();
  });
  await page.goto(`http://localhost:${PORT}/index.html`, { waitUntil: "load" });
  await page.waitForTimeout(1400);

  const out = await page.evaluate(async ([lat, lon]) => {
    document.getElementById("boot")?.remove();
    const F = window.__ghFifteen;

    // Tag classification, before anything else: it decides every count.
    const classified = {
      pharmacy: F.classify({ amenity: "pharmacy" }),
      school: F.classify({ amenity: "school" }),
      busStop: F.classify({ highway: "bus_stop" }),
      shop: F.classify({ shop: "convenience" }),
      park: F.classify({ leisure: "park" }),
      office: F.classify({ office: "company" }),
      church: F.classify({ amenity: "place_of_worship" }),
      nothing: F.classify({ highway: "residential" })
    };

    await F.run(lat, lon);
    const result = F.result();

    // The lens reads the same cached network.
    window.__ghLens.open();
    window.__ghLens.radius(400);
    const lensNear = window.__ghLens.state();
    // Three blocks east: still inside the fetched area, fewer places.
    window.__ghLens.move(lat, lon + 0.009);
    const lensFar = window.__ghLens.state();

    return { classified, result, lensNear, lensFar,
             axes: F.axes(), functions: F.functions(),
             status: F.status(),
             discDrawn: window.__ghLens.disc(),
             layers: window.__ghLayers.list().map((l) => l.label) };
  }, [LAT0, LON0]);

  await browser.close();
  server.close();

  const bad = [];
  const r = out.result;

  // Classification.
  if (out.classified.pharmacy !== "health") {
    bad.push(`a pharmacy was classified as ${out.classified.pharmacy}, not health`);
  }
  if (out.classified.school !== "education") bad.push("a school is not education");
  if (out.classified.busStop !== "transport") bad.push("a bus stop is not transport");
  if (out.classified.shop !== "retail") bad.push("a convenience shop is not retail");
  if (out.classified.park !== "green") bad.push("a park is not green");
  if (out.classified.office !== "employment") bad.push("an office is not employment");
  if (out.classified.church !== "culture") bad.push("a place of worship is not culture");
  if (out.classified.nothing !== null) bad.push("a plain street was classified as something");

  if (!r) {
    bad.push("the run produced no result: " + out.status);
  } else {
    // The grid has 169 nodes and 26 walkable ways; the motorway is excluded.
    if (r.nodes !== 169) bad.push(`the graph has ${r.nodes} nodes, not the grid's 169`);
    if (r.ways !== 26) bad.push(`${r.ways} ways were walked, not 26 — the motorway should be dropped`);

    if (r.bands.length !== 3) bad.push(`${r.bands.length} bands, not three`);
    const [b5, b10, b15] = r.bands;
    if (!(b5.areaKm2 < b10.areaKm2 && b10.areaKm2 < b15.areaKm2)) {
      bad.push(`the bands do not nest: ${r.bands.map((b) => b.areaKm2.toFixed(2)).join(" ")}`);
    }
    // 5 minutes is 400 m along the streets. On a 200 m grid that is a
    // diamond two blocks across, so well under the 0.50 km² of the circle a
    // crow-fly buffer would give, and well over nothing.
    if (!(b5.areaKm2 > 0.05 && b5.areaKm2 < 0.55)) {
      bad.push(`the 5-minute catchment is ${b5.areaKm2.toFixed(2)} km², which is not `
             + "a 400 m walk on a 200 m grid");
    }
    // A diamond, not a disc: the ratio of the walked area to the crow-fly
    // circle of the same radius is about 0.5 for a Manhattan grid. If this
    // comes out near 1, the catchment is a buffer and nothing was walked.
    const circle15 = Math.PI * 1.2 * 1.2;
    const ratio = b15.areaKm2 / circle15;
    if (ratio > 0.8) {
      bad.push(`the 15-minute catchment is ${(ratio * 100).toFixed(0)}% of the `
             + "crow-fly circle, so it is a buffer rather than a walk");
    }
    if (!b15.intersections) bad.push("no intersections were counted on a grid of streets");
    if (!(b15.streetKm > 1)) bad.push(`only ${b15.streetKm} km of street was reachable`);

    // Counts. Nine places are inside, one is 7 km away and must not be.
    if (r.within !== 11) {
      bad.push(`${r.within} places were counted inside, not the 11 placed there`);
    }
    if (r.counts.health !== 1) bad.push(`healthcare counted ${r.counts.health}, not 1 — `
      + "the hospital 7 km away must not be in a 15-minute catchment");
    if (r.counts.retail !== 4) bad.push(`retail counted ${r.counts.retail}, not 4`);
    if (r.counts.education !== 3) bad.push(`education counted ${r.counts.education}, not 3`);

    // Within 10 minutes: retail, transport, education, healthcare — every
    // essential. Green is at 1000 m, which is 12.5 minutes, so not in the 10.
    if (r.counts10.green !== 0) {
      bad.push("a park 1,000 m away was counted inside the 10-minute band");
    }

    // The axes.
    for (const axis of ["coverage", "density", "diversity", "essentials", "choice", "network"]) {
      const v = r.radar[axis];
      if (typeof v !== "number" || !Number.isFinite(v) || v < 0 || v > 100) {
        bad.push(`the ${axis} axis is ${v}`);
      }
    }
    // Five of seven functions are present: retail, education, health,
    // transport, green. Culture and employment are not.
    const want = (5 / 7) * 100;
    if (Math.abs(r.radar.coverage - want) > 0.5) {
      bad.push(`coverage is ${r.radar.coverage.toFixed(1)}, not ${want.toFixed(1)} for five of seven`);
    }
    if (r.radar.essentials !== 100) {
      bad.push(`every essential is within ten minutes, but essentials is ${r.radar.essentials}`);
    }
    // Healthcare and transport have one option each, so choice is not full.
    if (r.radar.choice >= 100) bad.push("choice is full though two functions have one option");
    if (!r.thin.includes("health")) bad.push("one clinic was not reported as thin provision");

    if (!r.reading.length) bad.push("the result has no reading");
    if (!r.reading.join(" ").match(/essential|reachable|choice/i)) {
      bad.push("the reading says nothing about what was found");
    }
  }

  if (!out.layers.some((l) => /15-minute/i.test(l))) {
    bad.push("the catchment was not added to the layer list");
  }
  if (!out.discDrawn) bad.push("the lens drew no disc on the map");
  if (out.lensNear.error) bad.push("the lens could not read the cached network: " + out.lensNear.error);
  if (!out.lensFar.error && out.lensFar.values) {
    const near = out.lensNear.values.coverage ?? 0;
    const far = out.lensFar.values.coverage ?? 0;
    if (near === far && near === 0) bad.push("the lens read nothing anywhere");
  }

  const real = errors.filter((e) => !/Failed to fetch|NetworkError|net::/i.test(e));
  if (real.length) bad.push("page errors: " + real.slice(0, 3).join(" | "));

  if (bad.length) {
    console.error("The 15-minute profile does not hold up:");
    for (const line of bad) console.error("  " + line);
    if (r) console.error("  radar: " + JSON.stringify(r.radar));
    process.exit(1);
  }

  console.log(`the 15-minute profile walks — ${r.nodes} nodes, ${r.ways} ways, `
    + `bands ${r.bands.map((b) => b.areaKm2.toFixed(2)).join("/")} km² nesting correctly `
    + `(${((r.bands[2].areaKm2 / (Math.PI * 1.44)) * 100).toFixed(0)}% of the crow-fly circle, `
    + `so it followed the streets); ${r.within} places in 5 of 7 functions; `
    + `coverage ${Math.round(r.radar.coverage)}, essentials ${Math.round(r.radar.essentials)}, `
    + `choice ${Math.round(r.radar.choice)}; the lens reads the same network`);
})();

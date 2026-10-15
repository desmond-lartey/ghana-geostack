/* Can it open your data?
 *
 * The complaint that prompted this was "I go to Data, try to add a CSV, and
 * nothing pops". So this opens one of each format the dialog claims to read
 * and checks a layer came out of it — and that a file it cannot read says why
 * rather than failing silently, which is the failure mode being fixed.
 */
const fs = require("fs");
const http = require("http");
const path = require("path");

const ROOT = path.join(__dirname, "..", "public");
const PORT = Number(process.env.SMOKE_PORT || 8129);

// getLayer must answer, because registerUserLayer keeps only the layer ids the
// map confirms; a stub that answers null gives every added layer none. The
// stub holds the sources and layers added to it, so it answers.
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

const GEOJSON = JSON.stringify({ type: "FeatureCollection", features: [
  { type: "Feature", properties: { name: "Kumasi", region: "Ashanti" },
    geometry: { type: "Point", coordinates: [-1.6163, 6.6885] } },
  { type: "Feature", properties: { name: "A patch" },
    geometry: { type: "Polygon", coordinates: [[[-1.7, 6.6], [-1.5, 6.6], [-1.5, 6.8], [-1.7, 6.6]]] } }
]});

// Quoted field with a comma in it, because real place names have them.
const CSV = 'name,district,lon,lat,people\n'
  + '"Accra, Central",Accra Metro,-0.1870,5.6037,2300000\n'
  + 'Tamale,Tamale Metro,-0.8393,9.4075,360579\n'
  + 'Nowhere,Unknown,,,0\n';

const GPX = `<?xml version="1.0"?><gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
  <wpt lat="6.6885" lon="-1.6163"><name>Borehole 12</name><ele>253</ele></wpt>
  <trk><name>Survey walk</name><trkseg>
    <trkpt lat="6.68" lon="-1.61"/><trkpt lat="6.69" lon="-1.60"/><trkpt lat="6.70" lon="-1.59"/>
  </trkseg></trk></gpx>`;

const KML = `<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>
  <Placemark><name>Clinic</name><Point><coordinates>-1.62,6.69,0</coordinates></Point></Placemark>
  <Placemark><name>Ward</name><Polygon><outerBoundaryIs><LinearRing><coordinates>
    -1.7,6.6,0 -1.5,6.6,0 -1.5,6.8,0 -1.7,6.6,0
  </coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark></Document></kml>`;

const WKT_CSV = 'id,wkt\n1,"POLYGON((-1.7 6.6, -1.5 6.6, -1.5 6.8, -1.7 6.6))"\n';

(async () => {
  if (!fs.existsSync(path.join(ROOT, "index.html"))) {
    console.error("public/index.html is missing. Run scripts/build_web.py first.");
    process.exit(1);
  }
  let chromium;
  try { ({ chromium } = require("playwright")); }
  catch {
    try { ({ chromium } = require("/home/claude/.npm-global/lib/node_modules/playwright")); }
    catch { console.log("playwright not installed, skipping the add-data test"); return; }
  }

  const server = await serve();
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1500, height: 860 } });
  await ctx.addInitScript(() => {
    try { localStorage.setItem("gh:safemode", "1"); sessionStorage.setItem("gh:recovered", "1"); }
    catch { /* blocked */ }
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
  await page.waitForTimeout(1300);

  const out = await page.evaluate(async (files) => {
    document.getElementById("boot")?.remove();
    const make = (name, text) => new File([text], name, { type: "text/plain" });
    const result = { added: [], status: {}, errors: {} };

    for (const [name, text] of Object.entries(files)) {
      const before = window.__ghLayers.list().length;
      await window.__ghAddData.files([make(name, text)]);
      const after = window.__ghLayers.list();
      result.status[name] = document.getElementById("adddata-status").innerText.trim();
      if (after.length > before) {
        const layer = after[after.length - 1];
        result.added.push({ file: name, label: layer.label, note: layer.note,
                            bbox: Boolean(layer.bbox), colour: Boolean(layer.colour) });
      } else {
        result.errors[name] = result.status[name];
      }
    }

    // Something it cannot read must say so, not fail quietly.
    const before = window.__ghLayers.list().length;
    await window.__ghAddData.files([make("notes.txt", "this is not data at all")]);
    result.refusedSaid = document.getElementById("adddata-status").innerText.trim();
    result.refusedAddedNothing = window.__ghLayers.list().length === before;

    // A real drop, dispatched the way a browser dispatches one. The handler
    // used to be on the map alone, so a file let go two pixels into the layer
    // list went to the browser, which navigated to it and threw the session
    // away. The target is the window now, and this drops on the ribbon —
    // about as far from the map as it is possible to get.
    const dropped = new DataTransfer();
    dropped.items.add(new File(['{"type":"FeatureCollection","features":['
      + '{"type":"Feature","properties":{"name":"Ho"},'
      + '"geometry":{"type":"Point","coordinates":[0.4713,6.6008]}}]}'],
      "dropped.geojson", { type: "application/geo+json" }));

    const onRibbon = document.getElementById("ribbon") || document.body;
    const beforeDrop = window.__ghLayers.list().length;
    for (const type of ["dragenter", "dragover"]) {
      onRibbon.dispatchEvent(new DragEvent(type,
        { bubbles: true, cancelable: true, dataTransfer: dropped }));
    }
    result.veilShown = !document.getElementById("drop-veil").hidden;
    const drop = new DragEvent("drop",
      { bubbles: true, cancelable: true, dataTransfer: dropped });
    onRibbon.dispatchEvent(drop);
    // A drop the page did not accept is a drop the browser will act on.
    result.dropPrevented = drop.defaultPrevented;
    await new Promise((r) => setTimeout(r, 500));
    result.dropAdded = window.__ghLayers.list().length - beforeDrop;
    result.veilHidden = document.getElementById("drop-veil").hidden;

    // The drop veil exists and the map listens for a drop.
    result.hasVeil = Boolean(document.getElementById("drop-veil"));

    // Changing the basemap replaces the whole style, which removes every
    // source and layer on the map. What the session added has to come back, or
    // picking a different background silently throws your data away.
    const drawnBefore = window.__ghBasemap.drawn();
    window.__ghBasemap.set("osm");
    await new Promise((r) => setTimeout(r, 600));
    result.basemap = {
      id: window.__ghBasemap.current(),
      before: drawnBefore,
      after: window.__ghBasemap.drawn(),
      gallery: window.__ghBasemap.gallery().length
    };
    return result;
  }, { "places.geojson": GEOJSON, "towns.csv": CSV, "survey.gpx": GPX,
       "wards.kml": KML, "shapes.csv": WKT_CSV });

  await browser.close();
  server.close();

  const bad = [];
  const expect = ["places.geojson", "towns.csv", "survey.gpx", "wards.kml", "shapes.csv"];
  for (const name of expect) {
    const got = out.added.find((a) => a.file === name);
    if (!got) bad.push(`${name} added no layer — ${out.errors[name] || "no reason given"}`);
    else if (!got.bbox) bad.push(`${name} produced a layer with no extent`);
  }
  // The CSV has three rows, one without a coordinate.
  const csv = out.added.find((a) => a.file === "towns.csv");
  if (csv && !/2 of 3/.test(csv.note || "")) {
    bad.push(`the CSV should report 2 of 3 rows, said "${csv.note}"`);
  }
  if (!out.refusedAddedNothing) bad.push("a file it cannot read still added a layer");
  if (!/not GeoJSON|no rows|coordinates/i.test(out.refusedSaid || "")) {
    bad.push(`an unreadable file did not say why: "${out.refusedSaid}"`);
  }
  if (!out.hasVeil) bad.push("there is no drop target on the map");
  if (!out.veilShown) bad.push("dragging a file over the ribbon showed no drop target");
  if (!out.dropPrevented) {
    bad.push("the drop was not accepted, so the browser would have opened the file "
           + "and thrown the session away");
  }
  if (out.dropAdded !== 1) bad.push(`dropping a file added ${out.dropAdded} layers, not 1`);
  if (!out.veilHidden) bad.push("the drop target stayed on screen after the drop");
  const bm = out.basemap || {};
  if (bm.id !== "osm") bad.push(`the basemap did not change, it is "${bm.id}"`);
  else if (!bm.before) bad.push("nothing was drawn before the basemap changed, so this proves nothing");
  else if (bm.after < bm.before) {
    bad.push(`changing the basemap lost layers — ${bm.before} drawn before, ${bm.after} after`);
  }
  const real = errors.filter((e) => !/Failed to fetch|NetworkError|net::/i.test(e));
  if (real.length) bad.push("page errors: " + real.slice(0, 3).join(" | "));

  if (bad.length) {
    console.error("Adding your own data does not work:");
    for (const line of bad) console.error("  " + line);
    process.exit(1);
  }
  console.log("a file dropped on the ribbon lands on the map, and the browser "
    + "does not navigate to it");
  console.log("add data works — " + out.added.map((a) => `${a.file} (${a.note})`).join(", "));
  console.log(`changing the basemap keeps them — ${out.basemap.before} drawn, `
    + `${out.basemap.after} after switching to ${out.basemap.id}`);
})();

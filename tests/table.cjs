/* Can you open a table of the data you have open?
 *
 * "Why can't I open a table of a dataset I have opened like RustGIS" — and
 * the answer was that Attribute Table opened the SQL workspace and typed a
 * comment into it. A button that names a thing and does something adjacent to
 * it is worse than one that does nothing, because nothing at least reads as
 * broken.
 *
 * So: open it on a real layer, and check the rows are there, the fields were
 * typed, sorting sorts, the filter filters, a clicked row selects and lights
 * up on the map, and the CSV comes out.
 */
const fs = require("fs");
const http = require("http");
const path = require("path");

const ROOT = path.join(__dirname, "..", "public");
const PORT = Number(process.env.SMOKE_PORT || 8131);
const { baseStub, patch } = require("./stub.cjs");
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

// Six districts with a name, a region and an area — enough to sort a number,
// sort a string, filter, and have a blank cell that must not sort as zero.
const CSV = "name,region,area_sqkm,capital\n"
  + "Bolgatanga,Upper East,729,Bolgatanga\n"
  + "Kumasi Metro,Ashanti,214,Kumasi\n"
  + "Wa Municipal,Upper West,1180,Wa\n"
  + "Accra Metro,Greater Accra,139,Accra\n"
  + "Tamale Metro,Northern,646,Tamale\n"
  + "Sekondi-Takoradi,Western,385,Sekondi\n";

const GEOJSON = JSON.stringify({ type: "FeatureCollection", features:
  CSV.trim().split("\n").slice(1).map((line, i) => {
    const [name, region, area, capital] = line.split(",");
    return { type: "Feature",
             properties: { name, region, area_sqkm: Number(area), capital,
                           // One blank, to prove a blank is not a zero.
                           note: i === 2 ? "" : `row ${i + 1}` },
             geometry: { type: "Point", coordinates: [-1.2 - i * 0.3, 6.2 + i * 0.6] } };
  })
});

(async () => {
  if (!fs.existsSync(path.join(ROOT, "index.html"))) {
    console.error("public/index.html is missing. Run scripts/build_web.py first.");
    process.exit(1);
  }
  let chromium;
  try { ({ chromium } = require("playwright")); }
  catch {
    try { ({ chromium } = require("/home/claude/.npm-global/lib/node_modules/playwright")); }
    catch { console.log("playwright not installed, skipping the table test"); return; }
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

  await page.route("**", (r) => {
    const u = r.request().url();
    if (/maplibre-gl@/.test(u)) {
      return r.fulfill({ status: 200, contentType: "application/javascript", body: STUB });
    }
    if (u.startsWith(`http://localhost:${PORT}`)) return r.continue();
    return r.abort();
  });
  await page.goto(`http://localhost:${PORT}/index.html`, { waitUntil: "load" });
  await page.waitForTimeout(1400);

  const out = await page.evaluate(async (geojson) => {
    document.getElementById("boot")?.remove();
    await window.__ghAddData.files([new File([geojson], "districts.geojson",
                                             { type: "application/geo+json" })]);
    const layer = window.__ghLayers.list().slice(-1)[0];
    await window.__ghTable.open(layer.id);
    await new Promise((r) => requestAnimationFrame(r));

    const read = () => [...document.querySelectorAll("#table-body tr[data-row]")]
      .map((tr) => [...tr.querySelectorAll("td")].map((td) => td.textContent.trim()));

    const opened = window.__ghTable.state();
    const first = read();

    // The header row names every field.
    const headers = [...document.querySelectorAll("#table-head th")]
      .map((th) => th.textContent.replace(/[↑↓]/g, "").trim());

    // Sort by a number, ascending. 139 must come first, not "1180" because
    // it starts with a 1.
    window.__ghTable.sort("area_sqkm", true);
    const ascending = read().map((r) => r[3]);

    window.__ghTable.sort("area_sqkm", false);
    const descending = read().map((r) => r[3]);

    // Filter.
    window.__ghTable.filter("upper");
    const filtered = read().length;
    window.__ghTable.filter("");

    // Clicking a row selects it and draws it on the map.
    const before = window.__ghTable.highlighted();
    document.querySelector("#table-body tr[data-row]")?.click();
    const after = window.__ghTable.state();
    const highlighted = window.__ghTable.highlighted();

    // A raster has no rows, and must say so rather than opening an empty grid.
    window.__ghLayers.add({ id: "fake-raster", label: "Active fire detections",
                            kind: "raster", layerIds: [], sourceId: "none" });
    window.__ghTable.close();
    await window.__ghTable.open("fake-raster");
    const rasterSaid = document.getElementById("sb-status")?.textContent
      || document.getElementById("status")?.textContent || "";
    const rasterOpened = !document.getElementById("table-dock").hidden;

    return { opened, headers, rows: first.length, cells: first[0],
             ascending, descending, filtered,
             selected: after.selected, before, highlighted,
             rasterSaid, rasterOpened,
             log: (window.__ghLog || []).slice(-6).map((l) => l.message) };
  }, GEOJSON);

  await browser.close();
  server.close();

  const bad = [];
  if (out.opened.rows !== 6) bad.push(`opened with ${out.opened.rows} rows, not 6`);
  if (out.rows !== 6) bad.push(`${out.rows} rows rendered, not 6`);
  if (!out.headers.includes("OID")) bad.push("no OID column");
  for (const field of ["name", "region", "area_sqkm", "capital"]) {
    if (!out.headers.includes(field)) bad.push(`the ${field} column is missing`);
  }
  if (!out.opened.fields.includes("area_sqkm:number")) {
    bad.push(`area_sqkm was not typed as a number: ${out.opened.fields.join(", ")}`);
  }
  if (!out.opened.fields.includes("name:text")) bad.push("name was not typed as text");

  // 139, 214, 385, 646, 729, 1180 — numeric order, not "1180" first.
  const want = ["139", "214", "385", "646", "729", "1180"];
  if (JSON.stringify(out.ascending) !== JSON.stringify(want)) {
    bad.push(`a number column sorted as text: ${out.ascending.join(", ")}`);
  }
  if (JSON.stringify(out.descending) !== JSON.stringify([...want].reverse())) {
    bad.push(`descending did not reverse: ${out.descending.join(", ")}`);
  }
  if (out.filtered !== 2) bad.push(`filtering for "upper" left ${out.filtered} rows, not 2`);
  if (out.selected.length !== 1) bad.push(`clicking a row selected ${out.selected.length} rows`);
  if (out.before !== 0 || out.highlighted !== 1) {
    bad.push("the selected row was not drawn on the map");
  }
  if (out.rasterOpened) bad.push("a raster opened an empty attribute table");
  if (!/raster|pixels/i.test(out.rasterSaid)) {
    bad.push(`a raster did not explain itself: "${out.rasterSaid}"`);
  }

  const real = errors.filter((e) => !/Failed to fetch|NetworkError|net::/i.test(e));
  if (real.length) bad.push("page errors: " + real.slice(0, 3).join(" | "));

  if (bad.length) {
    console.error("The attribute table does not work:");
    for (const line of bad) console.error("  " + line);
    process.exit(1);
  }

  console.log(`the attribute table works — ${out.rows} rows, `
    + `${out.headers.length - 1} fields typed, numbers sort as numbers, `
    + `the filter cut 6 to ${out.filtered}, a clicked row lights up on the map`);
})();

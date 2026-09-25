/* Does a styled result explain itself?
 *
 * A choropleth with no legend is a picture of a country in colours. The map is
 * stubbed, but the parts under test are real: applyStyle reads the values from
 * what is rendered, works out the ramp, and renderLegend turns that into the
 * symbology. So the stub answers queryRenderedFeatures with real rows and
 * getLayer with a real layer, and the assertions are on the legend's text.
 */
const fs = require("fs");
const http = require("http");
const path = require("path");

const ROOT = path.join(__dirname, "..", "public");
const PORT = Number(process.env.SMOKE_PORT || 8126);

const VALUES = [1499.06, 1378.39, 1204.5, 1102.2, 998.7, 950.1, 902.4, 880.0];

// The map stub, with two methods taught to answer: the style needs values to
// classify and a layer to paint.
const STUB = fs.readFileSync(path.join(__dirname, "smoke_viewer.cjs"), "utf8")
  .split("const STUB = `")[1].split("`;")[0]
  .replace("queryRenderedFeatures() { return []; }",
    `queryRenderedFeatures() { return ${JSON.stringify(
      VALUES.map((v) => ({ properties: { rainfall_mm: v } })))}; }`)
  .replace("getLayer() { return null; }", 'getLayer(id) { return { id, type: "fill" }; }');

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
    catch { console.log("playwright not installed, skipping the legend test"); return; }
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
  await page.waitForTimeout(1200);

  const out = await page.evaluate(() => {
    document.getElementById("boot")?.remove();
    const L = window.__ghLayers;
    L.add({ id: "qr", label: "Query result", kind: "result", colour: "#C2603C",
            layerIds: ["qr-fill"], sourceId: "qr", note: "16 regions" });
    L.add({ id: "ee-chirps", label: "CHIRPS Precipitation Daily", kind: "raster",
            layerIds: ["ee-chirps"], sourceId: "ee-chirps", note: "UCSB/CHG" });
    L.render();

    // What style_by_column does, through the tool the model calls.
    const styled = window.__ghTools && true;
    const result = window.__ghStyleByColumn
      ? null
      : null;
    return {
      styled,
      before: document.getElementById("legend-body").innerText,
      result
    };
  });

  // style_by_column is an agent tool, so it is driven as the agent drives it.
  const styling = await page.evaluate(async () =>
    window.__ghClip.tool("style_by_column", { column: "rainfall_mm", palette: "warm" }));

  const after = await page.evaluate(() => ({
    hidden: document.getElementById("legend").hidden,
    text: document.getElementById("legend-body").innerText.replace(/\s+/g, " ").trim(),
    classes: document.querySelectorAll("#legend-body .legend-group .legend-row").length
  }));

  await page.screenshot({ path: "/tmp/legend.png", clip: { x: 330, y: 380, width: 340, height: 470 } })
    .catch(() => {});
  await browser.close();
  server.close();

  const bad = [];
  if (typeof styling === "object" && styling?.error) bad.push("styling failed: " + styling.error);
  if (after.hidden) bad.push("the legend is hidden while three layers are drawn");
  if (!after.classes) bad.push("no classes were drawn for the graduated layer");
  // A range per class, the way a desktop GIS writes it.
  if (!/\d\s*–\s*\d/.test(after.text)) bad.push("the classes do not show their ranges");
  if (!/rainfall_mm/.test(after.text)) bad.push("the legend does not name the column it is coloured by");
  // The real minimum and maximum of the values the map rendered.
  if (!/880/.test(after.text)) bad.push("the legend does not show the low end (880)");
  if (!/1,499/.test(after.text)) bad.push("the legend does not show the high end (1,499)");
  if (!/equal count/.test(after.text)) bad.push("the legend does not say how it classified");
  if (!/CHIRPS/i.test(after.text)) bad.push("the raster is missing from the legend");
  // The heading is uppercased in CSS, so innerText comes back shouting.
  if (!/query result/i.test(after.text)) bad.push("the styled layer is not named");
  // Named once: as the heading of its own group, not also as a bare swatch.
  if ((after.text.match(/query result/gi) || []).length !== 1) {
    bad.push("the styled layer is listed twice");
  }
  // The ramp leads, because it is what the map is about.
  if (after.text.indexOf("rainfall_mm") > after.text.indexOf("CHIRPS")) {
    bad.push("the graduated layer does not come first");
  }
  if (bad.length) {
    console.error("The legend does not explain the map:");
    for (const line of bad) console.error("  " + line);
    console.error("  legend said: " + after.text);
    if (errors.length) console.error("  page errors: " + errors.slice(0, 3).join(" | "));
    process.exit(1);
  }
  console.log("the legend explains the map — ramp, column and range for the styled layer");
})();

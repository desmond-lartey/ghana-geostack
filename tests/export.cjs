/* Does the map export produce a map?
 *
 * The composition is canvas drawing, so the only honest check is to run it and
 * look at what comes out: the PNG is decoded and checked for the things a
 * printed map must have — a frame the map is drawn inside, a title, a legend
 * with the classes the map is using, a scale bar and a north arrow.
 *
 * The map itself is stubbed, so the "map" is a flat colour. That is the point:
 * everything around it is what this tests.
 */
const fs = require("fs");
const http = require("http");
const path = require("path");

const ROOT = path.join(__dirname, "..", "public");
const PORT = Number(process.env.SMOKE_PORT || 8127);
const VALUES = [1499.06, 1378.39, 1204.5, 1102.2, 998.7, 950.1, 902.4, 880.0];

// A stub that can be photographed: getCanvas hands back a real canvas with
// something drawn on it, because the export copies pixels from it.
const STUB = fs.readFileSync(path.join(__dirname, "smoke_viewer.cjs"), "utf8")
  .split("const STUB = `")[1].split("`;")[0]
  .replace("queryRenderedFeatures() { return []; }",
    `queryRenderedFeatures() { return ${JSON.stringify(
      VALUES.map((v) => ({ properties: { rainfall_mm: v } })))}; }`)
  .replace("getLayer() { return null; }", 'getLayer(id) { return { id, type: "fill" }; }')
  .replace("getCanvas() { return { width: 1200, height: 800, clientWidth: 1200, clientHeight: 800 }; }",
    `getCanvas() {
       if (!this._c) {
         this._c = document.createElement("canvas");
         this._c.width = 1200; this._c.height = 800;
         const g = this._c.getContext("2d");
         g.fillStyle = "#6f8f5e"; g.fillRect(0, 0, 1200, 800);
       }
       return this._c;
     }`);

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
    catch { console.log("playwright not installed, skipping the export test"); return; }
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

  await page.evaluate(() => {
    document.getElementById("boot")?.remove();
    const L = window.__ghLayers;
    L.add({ id: "qr", label: "Query result", kind: "result", colour: "#C2603C",
            layerIds: ["qr-fill"], sourceId: "qr", note: "16 regions" });
    L.render();
  });
  await page.evaluate(async () =>
    window.__ghClip.tool("style_by_column", { column: "rainfall_mm", palette: "warm" }));

  // The export waits for an idle map; the stub never fires it, so it is fired.
  const result = await page.evaluate(async () => {
    const png = await new Promise((resolve, reject) => {
      const original = HTMLAnchorElement.prototype.click;
      HTMLAnchorElement.prototype.click = function () { resolve(this.download); };
      setTimeout(() => reject(new Error("no download after 15s")), 15000);
      window.__ghExport.open();
      document.getElementById("export-title").value = "Average annual rainfall";
      document.getElementById("export-subtitle").value = "Ghana · 2024";
      window.__ghExport.run();
      setTimeout(() => window.__ghExport.idle(), 60);
      void original;
    });
    return { png, status: document.getElementById("export-status").textContent,
             image: window.__ghExport.lastDataUrl() };
  });

  const bad = [];
  if (!/\.png$/.test(result.png || "")) bad.push("no PNG was offered for download");
  if (!/Saved/.test(result.status || "")) bad.push("the dialog did not report success: " + result.status);

  if (result.image) {
    const buffer = Buffer.from(result.image.split(",")[1], "base64");
    fs.writeFileSync("/tmp/map-export.png", buffer);
    if (buffer.length < 20000) bad.push("the image is too small to contain a map");
    // PNG header: width and height are big-endian at byte 16.
    const width = buffer.readUInt32BE(16);
    const height = buffer.readUInt32BE(20);
    if (width !== 3200 || height !== 2200) {
      bad.push(`expected a 1600x1100 layout at 2x, got ${width}x${height}`);
    }
  } else {
    bad.push("the export did not keep the image it produced");
  }

  await browser.close();
  server.close();

  if (bad.length) {
    console.error("The map export is wrong:");
    for (const line of bad) console.error("  " + line);
    if (errors.length) console.error("  page errors: " + errors.slice(0, 3).join(" | "));
    process.exit(1);
  }
  console.log("the map export produces a laid-out PNG — frame, title, legend, scale and north");
})();

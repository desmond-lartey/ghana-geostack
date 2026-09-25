/* Does the viewer's script actually run?
 *
 * `node --check` proves the file parses. It does not prove it executes, and
 * the difference is not academic: a const referenced before its declaration
 * parses perfectly and throws the moment the module is evaluated, taking the
 * whole page with it. That is precisely how "Cannot access 'EE_PALETTES'
 * before initialization" reached production.
 *
 * The obstacle to catching it locally is that the page imports MapLibre from a
 * CDN, so on a machine without that CDN the module never runs at all and every
 * such fault is invisible. So the import is intercepted and answered with a
 * stub: enough of a map for the top-level code to complete, which is where
 * declaration-order faults live.
 *
 *     node tests/smoke_viewer.cjs [url]
 *
 * Exits non-zero on any uncaught error, and names it.
 */

const fs = require("fs");
const http = require("http");
const path = require("path");

const ROOT = path.join(__dirname, "..", "public");
const PORT = Number(process.env.SMOKE_PORT || 8123);

// Just enough MapLibre for the module body to finish. The load handler never
// fires, which is fine: this is about code that runs at evaluation time.
const STUB = `
const handlers = {};
class FakeMap {
  constructor() { this.style = { layers: [] }; }
  on(name, fn) { (handlers[name] ??= []).push(fn); return this; }
  once(name, fn) { return this.on(name, fn); }
  fire(name) { for (const fn of handlers[name] ?? []) fn({}); return this; }
  off() { return this; }
  addControl() { return this; }
  removeControl() { return this; }
  addSource() {} removeSource() {} addLayer() {} removeLayer() {}
  getSource() { return null; } getLayer() { return null; }
  getStyle() { return { layers: [] }; }
  setProjection() {} setTerrain() {} setPaintProperty() {}
  getPaintProperty() { return 1; } setLayoutProperty() {}
  getCenter() { return { lng: -1.09, lat: 7.95 }; }
  getZoom() { return 6.2; }
  getBearing() { return 0; }
  getPitch() { return 0; }
  getCanvas() { return { width: 1200, height: 800, clientWidth: 1200, clientHeight: 800 }; }
  getBounds() { return { getSouth: () => 4.7, getWest: () => -3.3,
                         getNorth: () => 11.2, getEast: () => 1.3,
                         toArray: () => [[-3.3, 4.7], [1.3, 11.2]] }; }
  flyTo() {} fitBounds() {} easeTo() {} jumpTo() {} resize() {}
  queryRenderedFeatures() { return []; }
  project() { return { x: 0, y: 0 }; }
  unproject() { return { lng: 0, lat: 0 }; }
}
class Noop { constructor() {} addTo() { return this; } remove() { return this; }
  setLngLat() { return this; } setHTML() { return this; } setDOMContent() { return this; } }
export default {
  Map: FakeMap, NavigationControl: Noop, ScaleControl: Noop, AttributionControl: Noop,
  Popup: Noop, Marker: Noop, GeolocateControl: Noop,
  LngLat: class { constructor(lng, lat) { this.lng = lng; this.lat = lat; }
                  wrap() { return this; } toArray() { return [this.lng, this.lat]; } },
  LngLatBounds: class { extend() { return this; } toArray() { return [[0,0],[0,0]]; } }
};
`;

function serve() {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const file = path.join(ROOT, req.url === "/" ? "index.html" : req.url.split("?")[0]);
      if (!fs.existsSync(file) || fs.statSync(file).isDirectory()) {
        res.writeHead(404); return res.end();
      }
      res.writeHead(200, {
        "content-type": file.endsWith(".html") ? "text/html"
                      : file.endsWith(".json") ? "application/json"
                      : "application/octet-stream"
      });
      fs.createReadStream(file).pipe(res);
    });
    server.listen(PORT, () => resolve(server));
  });
}

async function main() {
  if (!fs.existsSync(path.join(ROOT, "index.html"))) {
    console.error("public/index.html is missing. Run scripts/build_web.py first.");
    process.exit(1);
  }

  let chromium;
  try {
    ({ chromium } = require("playwright"));
  } catch {
    try {
      ({ chromium } = require(
        "/home/claude/.npm-global/lib/node_modules/playwright"));
    } catch {
      console.log("playwright not installed, skipping the smoke test");
      return;
    }
  }

  const server = await serve();
  const browser = await chromium.launch();
  const context = await browser.newContext();

  // Safe mode off the table: a reload mid-test would hide the thing being
  // tested behind a navigation.
  await context.addInitScript(() => {
    try {
      localStorage.setItem("gh:safemode", "1");
      sessionStorage.setItem("gh:recovered", "1");
    } catch { /* storage blocked */ }
  });

  const page = await context.newPage();
  const errors = [];
  // The stack matters more than the message: "cannot access X before
  // initialization" is useless without knowing who reached for X.
  page.on("pageerror", (err) => errors.push(
    err.stack ? `${err.message}\n      ${err.stack.split("\n").slice(1, 4).join("\n      ")}`
              : err.message));
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(`console: ${m.text().slice(0, 200)}`);
  });

  // One handler, because Playwright gives precedence to the most recently
  // added route: a separate catch-all registered afterwards would win and
  // abort the very request the stub exists to answer.
  await page.route("**", (route) => {
    const url = route.request().url();
    if (/maplibre-gl@/.test(url)) {
      return route.fulfill({ status: 200, contentType: "application/javascript", body: STUB });
    }
    if (url.startsWith(`http://localhost:${PORT}`)) return route.continue();
    return route.abort();      // nothing else may reach the network
  });

  await page.goto(`http://localhost:${PORT}/index.html`, { waitUntil: "load" })
    .catch((err) => errors.push(`navigation: ${err.message}`));
  await page.waitForTimeout(1500);

  // The module has its own scope, so nothing inside it is visible here except
  // what it deliberately exposes. Evidence that it finished is therefore taken
  // from what it did: the basemap list is filled from a constant at top level,
  // and the tool hook only exists once the agent section has been evaluated.
  const reached = await page.evaluate(() => {
    const specs = (() => {
      try { return window.__ghTools ? window.__ghTools() : null; }
      catch (e) { return `threw: ${e.message}`; }
    })();
    return {
      module_ran: document.getElementById("basemap-select")?.options.length > 0,
      tools: Array.isArray(specs) ? specs.length : 0,
      specs_ok: Array.isArray(specs)
        ? specs.every((s) => s.name && typeof s.description === "string" && s.input_schema)
        : `tool specs unavailable (${specs})`
    };
  }).catch((err) => ({ module_ran: false, error: err.message }));

  await browser.close();
  server.close();

  // Everything off-origin is aborted by design, so a message naming an
  // off-origin address is this harness refusing the network, not a fault in
  // the page. Anything else is real.
  const networkNoise =
    /ERR_FAILED|net::|aborted|Failed to fetch|NetworkError|Load failed|https?:\/\/(?!localhost)/i;
  const real = errors.filter((e) => !networkNoise.test(e));

  if (real.length) {
    console.error("The viewer threw while running:");
    for (const e of real.slice(0, 10)) console.error("  " + e);
    process.exit(1);
  }
  if (!reached.module_ran) {
    console.error("The module did not finish evaluating.", reached);
    process.exit(1);
  }
  if (reached.specs_ok !== true) {
    console.error("Tool specs are not well formed:", reached.specs_ok);
    process.exit(1);
  }

  console.log(`viewer runs clean — ${reached.tools} agent tools, specs well formed`);
}

main().catch((err) => { console.error(err); process.exit(1); });

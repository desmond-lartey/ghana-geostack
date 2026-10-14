/* The Ghana data library: does the catalogue say true things, and does
 * pressing Add actually add?
 *
 * Two distinct failures to catch. The first is a card that claims a layer is
 * ready and then does nothing when pressed - the catalogue would be
 * advertising. So every entry marked ready must carry a way to draw itself,
 * and a sample of them are added for real and must land on the map.
 *
 * The second is quieter: a card rendering as a strip. Every band of the card
 * is optional-looking to a layout engine, and the grid has twice collapsed
 * them - once to the thumbnail with no text, once to the text with no
 * thumbnail. Both looked deliberate in a screenshot and were not. So the card
 * is measured, not just counted.
 */
const fs = require("fs");
const http = require("http");
const path = require("path");

const ROOT = path.join(__dirname, "..", "public");
const PORT = Number(process.env.SMOKE_PORT || 8130);
const { baseStub, patch } = require("./stub.cjs");
const STUB = patch(baseStub(), [
  // A drawn layer keeps only the ids the map confirms, so the map must
  // confirm them.
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

(async () => {
  if (!fs.existsSync(path.join(ROOT, "index.html"))) {
    console.error("public/index.html is missing. Run scripts/build_web.py first.");
    process.exit(1);
  }
  let chromium;
  try { ({ chromium } = require("playwright")); }
  catch {
    try { ({ chromium } = require("/home/claude/.npm-global/lib/node_modules/playwright")); }
    catch { console.log("playwright not installed, skipping the library test"); return; }
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

  const out = await page.evaluate(async () => {
    document.getElementById("boot")?.remove();
    const entries = window.__ghLibrary.entries();
    window.__ghLibrary.open();
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));

    // Every band of a card must be on screen, inside the card, at a size a
    // person could read.
    const card = document.querySelector(".lib-card");
    const band = (sel) => {
      const el = card?.querySelector(sel);
      return el ? Math.round(el.getBoundingClientRect().height) : 0;
    };
    const shape = {
      card: card ? Math.round(card.getBoundingClientRect().height) : 0,
      thumb: band(".lib-thumb"), text: band(".lib-text"),
      foot: band(".lib-foot"), meta: band(".lib-meta")
    };
    // A card whose children spill past its own box is a card being clipped.
    const spill = card
      ? Math.round(shape.thumb + shape.text + shape.foot + shape.meta) - shape.card
      : 0;

    const all = window.__ghLibrary.shown();
    window.__ghLibrary.filter("theme", "Health");
    const health = window.__ghLibrary.shown();
    window.__ghLibrary.filter("theme", "");
    window.__ghLibrary.filter("search", "flood");
    const flood = window.__ghLibrary.shown();
    window.__ghLibrary.filter("search", "");

    // Two that say they are ready, and one that says it is not. The two are
    // GIBS rasters rather than boundaries, because the boundaries need their
    // GeoJSON and this page is running against a stubbed map.
    const before = window.__ghLayers.list().length;
    const catalogBefore = new Set(window.__ghLayers.catalog());
    window.__ghLibrary.pick("lib.nightlights");
    window.__ghLibrary.pick("lib.truecolor");
    window.__ghLibrary.pick("lib.health15");
    await window.__ghLibrary.add();
    await new Promise((r) => setTimeout(r, 400));

    return {
      entries, shape, spill, all, health, flood,
      themes: [...new Set(entries.map((e) => e.theme))],
      closed: document.getElementById("library").hidden,
      // Catalogue layers turn on in state.active; everything else arrives as
      // a user layer. Either is "it landed".
      drawn: window.__ghLayers.catalog().filter((id) => !catalogBefore.has(id)),
      layersGained: window.__ghLayers.list().length - before,
      log: (window.__ghLog || []).slice(-8).map((l) => `${l.kind}: ${l.message}`)
    };
  });

  await browser.close();
  server.close();

  const bad = [];

  // Shape.
  if (!out.shape.thumb) bad.push("the cards have no thumbnail");
  if (out.shape.thumb && out.shape.thumb < 80) {
    bad.push(`the thumbnail is ${out.shape.thumb}px tall, which is a strip`);
  }
  if (out.shape.text < 40) bad.push(`the card text is ${out.shape.text}px tall`);
  if (!out.shape.foot) bad.push("the cards have no Add button row");
  if (!out.shape.meta) bad.push("the cards do not show their source and licence");
  if (out.spill > 2) {
    bad.push(`the card is ${out.shape.card}px but holds ${out.shape.card + out.spill}px `
           + "of content, so it is being clipped");
  }

  // Catalogue.
  if (out.entries.length < 25) bad.push(`only ${out.entries.length} layers in the library`);
  if (out.themes.length < 8) bad.push(`only ${out.themes.length} themes`);
  const ready = out.entries.filter((e) => e.status === "ready");
  const liars = ready.filter((e) => !e.actionable);
  if (liars.length) {
    bad.push("says ready but cannot draw: " + liars.map((e) => e.id).join(", "));
  }
  const unsourced = out.entries.filter((e) => !e.source || !e.licence);
  if (unsourced.length) {
    bad.push("no source or licence: " + unsourced.map((e) => e.id).join(", "));
  }
  // The analysis-ready products are the reason this exists.
  for (const want of ["lib.health15", "lib.flood-exposure", "lib.market-access"]) {
    if (!out.entries.some((e) => e.id === want)) bad.push(`${want} is missing`);
  }

  // Filters.
  if (out.health >= out.all) bad.push("the theme filter did not narrow anything");
  if (!out.health) bad.push("the theme filter removed everything");
  if (!out.flood || out.flood >= out.all) bad.push(`searching "flood" showed ${out.flood} of ${out.all}`);

  // Adding.
  if (!out.closed) bad.push("the picker stayed open after adding");
  if (out.drawn.length < 2) {
    bad.push(`adding two ready layers drew ${out.drawn.length} of them`);
  }
  if (!out.log.some((l) => /not yet|not built|needs/i.test(l))) {
    bad.push("a layer that is not built was added without saying so");
  }

  const real = errors.filter((e) => !/Failed to fetch|NetworkError|net::/i.test(e));
  if (real.length) bad.push("page errors: " + real.slice(0, 3).join(" | "));

  if (bad.length) {
    console.error("The Ghana data library does not hold up:");
    for (const line of bad) console.error("  " + line);
    process.exit(1);
  }

  console.log(`the Ghana library holds - ${out.entries.length} layers across `
    + `${out.themes.length} themes, ${ready.length} ready and all of them drawable; `
    + `cards ${out.shape.card}px with every band; `
    + `added ${out.drawn.length} and said why not for the rest`);
})();

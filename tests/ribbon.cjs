/* The ribbon, and whether its commands are what they claim to be.
 *
 * A ribbon is a promise: every control says it does something. Three hundred
 * controls is three hundred chances for a label to outlive its function, so
 * this runs every command that claims to be built and fails on the first one
 * that throws. The slots — commands with no implementation — are checked too,
 * but for the opposite thing: that they say so rather than failing silently.
 */
const fs = require("fs");
const http = require("http");
const path = require("path");

const ROOT = path.join(__dirname, "..", "public");
const PORT = Number(process.env.SMOKE_PORT || 8128);
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
    catch { console.log("playwright not installed, skipping the ribbon test"); return; }
  }

  const server = await serve();
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 } });
  await ctx.addInitScript(() => {
    try { localStorage.setItem("gh:safemode", "1"); sessionStorage.setItem("gh:recovered", "1"); }
    catch { /* blocked */ }
  });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  // A command that asks a question must not stop the run.
  page.on("dialog", (d) => d.dismiss().catch(() => {}));

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

  const shape = await page.evaluate(() => {
    document.getElementById("boot")?.remove();
    const spec = window.__ghRibbon.spec();
    const cmds = window.__ghRibbon.commands();
    const declared = new Set();
    for (const t of spec) for (const g of t.groups) for (const c of g.controls) declared.add(c.cmd);
    return {
      tabs: spec.map((t) => t.tab),
      groups: spec.reduce((n, t) => n + t.groups.length, 0),
      controls: spec.reduce((n, t) => n + t.groups.reduce((m, g) => m + g.controls.length, 0), 0),
      commands: cmds.length,
      built: cmds.filter((c) => c.built).length,
      // Every control on the ribbon must name a command that exists.
      orphans: [...declared].filter((id) => !cmds.some((c) => c.id === id))
    };
  });

  // Every built command, run. window.open is stubbed so a command that opens
  // documentation does not open a browser tab per call.
  const ran = await page.evaluate(async () => {
    window.open = () => null;
    const out = { ok: [], threw: [] };
    for (const c of window.__ghRibbon.commands().filter((x) => x.built)) {
      try {
        await window.__ghRibbon.run(c.id);
        out.ok.push(c.id);
      } catch (err) {
        out.threw.push(`${c.id}: ${err && err.message ? err.message : err}`);
      }
      await new Promise((r) => setTimeout(r, 0));
    }
    return out;
  });

  // The widest tab must not widen the window. A grid item's min-width is
  // auto, so a ribbon wider than the screen once stretched the whole shell and
  // pushed the right-hand dock thousands of pixels off the side of it.
  const fits = await page.evaluate(() => {
    const out = [];
    for (const tab of window.__ghRibbon.spec()) {
      document.querySelector(`.ribbon-tab[data-tab="${tab.tab}"]`)?.click();
      const panel = document.getElementById("panel");
      panel.hidden = false;
      const box = panel.getBoundingClientRect();
      if (box.right > window.innerWidth + 1) {
        out.push(`${tab.tab}: the right dock ends at ${Math.round(box.right)}px `
               + `in a ${window.innerWidth}px window`);
      }
      if (document.documentElement.scrollWidth > window.innerWidth + 1) {
        out.push(`${tab.tab}: the page scrolls sideways `
               + `(${document.documentElement.scrollWidth}px)`);
      }
    }
    return out;
  });

  // A slot must explain itself rather than do nothing.
  const slot = await page.evaluate(() => {
    const planned = window.__ghRibbon.commands().find((c) => !c.built);
    if (!planned) return { none: true };
    window.__ghRibbon.run(planned.id);
    const pane = document.getElementById("pane-planned");
    return { id: planned.id, shown: pane?.dataset.active === "true",
             mentionsId: (pane?.innerText || "").includes(planned.id) };
  });

  await browser.close();
  server.close();

  const bad = [];
  if (shape.tabs.length !== 10) bad.push(`expected ten tabs, got ${shape.tabs.join(", ")}`);
  if (shape.orphans.length) bad.push("controls naming no command: " + shape.orphans.join(", "));
  if (ran.threw.length) bad.push("commands that threw:\n    " + ran.threw.join("\n    "));
  if (fits.length) bad.push("the ribbon pushes the shell off screen:\n    " + fits.join("\n    "));
  if (!slot.shown) bad.push("a slot did not open its explainer");
  if (!slot.mentionsId) bad.push("the explainer does not give the command id");
  // Uncaught page errors during the sweep mean a command broke something else.
  const real = errors.filter((e) => !/Failed to fetch|NetworkError|net::/i.test(e));
  if (real.length) bad.push("page errors: " + real.slice(0, 4).join(" | "));

  if (bad.length) {
    console.error("The ribbon does not hold together:");
    for (const line of bad) console.error("  " + line);
    process.exit(1);
  }
  console.log(`ribbon holds — ${shape.tabs.length} tabs, ${shape.groups} groups, `
    + `${shape.controls} controls, ${shape.commands} commands, `
    + `${shape.built} built and all of them ran, ${shape.commands - shape.built} slots`);
})();

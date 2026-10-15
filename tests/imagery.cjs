/* Does the imagery search score correctly?
 *
 * No scene for Ghana exists yet — building one needs a GPU and gated weights
 * — so this makes a tiny one whose answer is known. Four quadrants, each
 * assigned a different unit vector, and prompts that are those same vectors.
 * A search for the prompt that matches quadrant two must light quadrant two
 * and nothing else.
 *
 * That is a fixture and not data, and it proves exactly one thing: the
 * arithmetic between a prompt and a patch is right. Whether DINOv3 thinks a
 * Ghanaian rooftop looks like the word "rooftop" is a question for the day
 * somebody builds a real scene, and no test here can answer it.
 */
const fs = require("fs");
const http = require("http");
const path = require("path");

const ROOT = path.join(__dirname, "..", "public");
const PORT = Number(process.env.SMOKE_PORT || 8134);
const { baseStub, patch } = require("./stub.cjs");
const STUB = patch(baseStub(), [
  ["getLayer(id) { return this._lyr.get(id) || null; }",
   'getLayer(id) { return this._lyr.get(id) || { id, type: "raster" }; }']
]);

const W = 16, H = 16, DIM = 8;

/* Four 8×8 quadrants, each given one basis vector so its cosine against
   "its own" prompt is 1 and against every other prompt 0.

   Three of the four are made to match a *background* prompt — water, road,
   trees — because that is what a real scene looks like and it is what the
   correction is for. A first version gave the other quadrants vectors that
   matched nothing at all, and they all scored 0.25: with three backgrounds
   and no information anywhere, 1/(1+3) is the right answer and the test
   proved nothing. A patch that looks like water has to score near zero for
   "north east", and now one does. */
function scene() {
  // quadrant 0 is water, 1 is the thing being searched for, 2 is road,
  // 3 is trees.
  const assigned = [4, 1, 5, 6];
  const codes = new Uint8Array(W * H * DIM);
  for (let y = 0; y < H; y += 1) {
    for (let x = 0; x < W; x += 1) {
      const q = (y < H / 2 ? 0 : 2) + (x < W / 2 ? 0 : 1);
      const i = (y * W + x) * DIM;
      // Stored as uint8 around 128; scale 1/127 puts 255 at +1.
      for (let d = 0; d < DIM; d += 1) codes[i + d] = 128;
      codes[i + assigned[q]] = 255;
    }
  }
  const basis = (k) => Array.from({ length: DIM }, (_, d) => (d === k ? 1 : 0));
  return {
    manifest: {
      name: "Test quadrants",
      bounds: [-1.70, 6.65, -1.55, 6.75],
      width: W, height: H, dim: DIM, patch_metres: 10,
      embeddings: "scene.u8", prompts: "prompts.json",
      scale: 1 / 127, logit_scale: 100,
      attribution: "A fixture, not imagery."
    },
    codes,
    prompts: {
      "north west": basis(0), "north east": basis(1),
      "south west": basis(2), "south east": basis(3),
      water: basis(4), road: basis(5), trees: basis(6)
    }
  };
}

function serve(fixture) {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const url = req.url.split("?")[0];
      if (url === "/fixture/scene.json") {
        res.writeHead(200, { "content-type": "application/json" });
        return res.end(JSON.stringify(fixture.manifest));
      }
      if (url === "/fixture/scene.u8") {
        res.writeHead(200, { "content-type": "application/octet-stream" });
        return res.end(Buffer.from(fixture.codes));
      }
      if (url === "/fixture/prompts.json") {
        res.writeHead(200, { "content-type": "application/json" });
        return res.end(JSON.stringify(fixture.prompts));
      }
      const file = path.join(ROOT, url === "/" ? "index.html" : url);
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
    catch { console.log("playwright not installed, skipping the imagery test"); return; }
  }

  const fixture = scene();
  const server = await serve(fixture);
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 860 } });
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

  const out = await page.evaluate(async ([port, w, h]) => {
    document.getElementById("boot")?.remove();
    const I = window.__ghImagery;

    const before = I.scene();
    await I.load(`http://localhost:${port}/fixture/scene.json`);
    const loaded = I.scene();
    if (!loaded) return { before, loaded, loadError: I.status() };

    I.set("background", ["water", "road", "trees"]);
    I.set("threshold", 0.5);
    const result = I.search("north east");
    const scores = I.scores();

    // The mean score of each quadrant. Quadrant 1 (north east on the map is
    // the top right of the array, which is row < h/2, col >= w/2) must be
    // high and the rest low.
    const means = [0, 0, 0, 0].map(() => 0);
    const counts = [0, 0, 0, 0];
    for (let y = 0; y < h; y += 1) {
      for (let x = 0; x < w; x += 1) {
        const q = (y < h / 2 ? 0 : 2) + (x < w / 2 ? 0 : 1);
        means[q] += scores[y * w + x];
        counts[q] += 1;
      }
    }
    for (let q = 0; q < 4; q += 1) means[q] /= counts[q];

    const unknown = I.search("aircraft carrier");
    const status = I.status();

    return { before, loaded, means, drawn: I.drawn(),
             relative: result.relative, unknownError: unknown.error, status,
             layers: window.__ghLayers.list().map((l) => l.label) };
  }, [PORT, W, H]);

  await browser.close();
  server.close();

  const bad = [];
  if (out.before) bad.push("a scene was loaded before one was asked for");
  if (!out.loaded) bad.push("the fixture scene did not load: " + (out.loadError || ""));
  else {
    if (out.loaded.patches !== W * H) {
      bad.push(`${out.loaded.patches} patches loaded, not ${W * H}`);
    }
    if (out.loaded.dim !== DIM) bad.push(`dim is ${out.loaded.dim}, not ${DIM}`);
    if (out.loaded.prompts.length !== 7) {
      bad.push(`${out.loaded.prompts.length} prompts, not 7`);
    }
  }

  if (out.means) {
    const [nw, ne, sw, se] = out.means;
    if (!(ne > 0.9)) bad.push(`the matching quadrant scored ${ne.toFixed(3)}, not near 1`);
    for (const [name, v] of [["north west", nw], ["south west", sw], ["south east", se]]) {
      // Near zero, because each of these matches a background prompt
      // strongly — which is exactly what the correction is supposed to do.
      if (v > 0.05) {
        bad.push(`${name} looks like a background prompt but still scored `
               + `${v.toFixed(3)} for "north east"`);
      }
    }
    if (!(ne > 0.9 && Math.max(nw, sw, se) < 0.05)) {
      bad.push(`the matching quadrant is not distinguished: ${out.means.map((m) => m.toFixed(2)).join(" ")}`);
    }
  } else {
    bad.push("no scores came back");
  }

  if (!out.relative) bad.push("the score was not corrected against the background prompts");
  if (!out.drawn) bad.push("no heatmap was drawn on the map");
  if (!out.layers.some((l) => /imagery search/i.test(l))) {
    bad.push("the heatmap did not become a layer");
  }
  // A prompt with no precomputed vector must say so rather than scoring zero.
  if (!/not among|precomputed/i.test(out.unknownError || "")) {
    bad.push(`an unknown prompt did not explain itself: "${out.unknownError}"`);
  }

  const real = errors.filter((e) => !/Failed to fetch|NetworkError|net::/i.test(e));
  if (real.length) bad.push("page errors: " + real.slice(0, 3).join(" | "));

  if (bad.length) {
    console.error("The imagery search does not score correctly:");
    for (const line of bad) console.error("  " + line);
    if (out.means) console.error("  quadrant means: " + out.means.map((m) => m.toFixed(3)).join(", "));
    process.exit(1);
  }

  console.log(`imagery search scores — a ${W}×${H}×${DIM} fixture scene loaded, the `
    + `matching quadrant scored ${out.means[1].toFixed(2)} against `
    + `${Math.max(out.means[0], out.means[2], out.means[3]).toFixed(2)} for the rest, `
    + `corrected against three background prompts; an unknown prompt says so`);
})();

/* Does the Earth Engine clip use this page's own boundary?
 *
 * Earth Engine cannot be reached from a test, so `ee` is stubbed with a
 * recorder: every call is logged with its arguments, and the assertions are
 * about the expression that was built. That is exactly where both bugs lived —
 * a name sent to a boundary asset that had never heard of it, and a failure
 * that returned nothing while the caller reported success.
 */
const fs = require("fs");
const http = require("http");
const path = require("path");

const ROOT = path.join(__dirname, "..", "public");
const PORT = Number(process.env.SMOKE_PORT || 8124);
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

(async()=>{
 if (!fs.existsSync(path.join(ROOT, "index.html"))) {
   console.error("public/index.html is missing. Run scripts/build_web.py first.");
   process.exit(1);
 }
 let chromium;
 try { ({ chromium } = require("playwright")); }
 catch {
   try { ({ chromium } = require("/home/claude/.npm-global/lib/node_modules/playwright")); }
   catch { console.log("playwright not installed, skipping the Earth Engine clip test"); return; }
 }
 const server = await serve();
 const b=await chromium.launch(); const ctx=await b.newContext({viewport:{width:1400,height:820}});
 await ctx.addInitScript(()=>{try{localStorage.setItem('gh:safemode','1');sessionStorage.setItem('gh:recovered','1');}catch{}});
 const p=await ctx.newPage();
 p.on('pageerror',e=>console.log('PAGEERROR',e.message));
 await p.route("**",(r)=>{const u=r.request().url();
   if(/maplibre-gl@/.test(u)) return r.fulfill({status:200,contentType:"application/javascript",body:STUB});
   if(u.startsWith(`http://localhost:${PORT}`)) return r.continue(); return r.abort();});
 await p.goto(`http://localhost:${PORT}/index.html`,{waitUntil:'load'});
 await p.waitForTimeout(1200);

 const out = await p.evaluate(async () => {
   const calls = [];
   // A recorder rather than a hand-written stub: any method Earth Engine's
   // client offers returns another recorder, so the test does not fail the
   // day the page calls a method nobody listed here.
   const node = (kind, args) => {
     calls.push({ kind, args });
     const target = {
       __kind: kind, __args: args,
       size: () => ({ evaluate: (cb) => cb(3, null) }),
       evaluate: (cb) => cb(3, null),
       getMap: (o, cb) => cb({ urlFormat: "https://tiles/{z}/{x}/{y}" }, null)
     };
     return new Proxy(target, {
       // `then` must stay undefined. Awaiting a value whose `then` is a
       // function makes JavaScript treat it as a promise and call it, so a
       // recorder that answers every property turns `await someEeObject` into
       // a wait for a resolve that never comes.
       get: (t, prop) => prop === "then" ? undefined
         : prop in t ? t[prop]
         : (typeof prop === "string" ? (...a) => node(prop, a) : undefined)
     });
   };
   const ee = {
     ImageCollection: (id) => node("ImageCollection", [id]),
     Image: (id) => node("Image", [id]),
     FeatureCollection: (x) => node("FeatureCollection", [x]),
     Feature: (g) => node("Feature", [g]),
     Geometry: (g) => node("Geometry", [g]),
     Filter: { eq: (k, v) => ({ __filter: [k, v] }) },
     Date: (d) => ({ advance: () => ({ __date: d }) }),
     Reducer: { frequencyHistogram: () => ({}), sum: () => ({}), mean: () => ({}) }
   };
   window.ee = ee;

   const st = window.__ghClip;
   if (!st) return { error: "no clip hook" };

   // Pretend Earth Engine is connected, and hand the page a boundary the way
   // the database would.
   st.setReady(true);
   const oti = { type: "Polygon", coordinates: [[[0.2,7.6],[0.6,7.6],[0.6,8.4],[0.2,8.4],[0.2,7.6]]] };
   st.setClip({ kind: "region", name: "Oti", geometry: oti });

   const dataset = { id: "ESA/WorldCover/v200", title: "ESA WorldCover 10m v200",
                     type: "image_collection", provider: "ESA",
                     classes: { band: "Map", values: [10, 20], colours: ["006400","ffbb22"],
                                names: ["Tree cover","Shrubland"] } };
   const result = await st.addLayer(dataset, { start: "2021-01-01", end: "2021-12-31",
     bands: ["Map"], reducer: "mosaic", min: "", max: "", palette: [] });

   const names = calls.map(c => c.kind);
   const shapeNameFilters = calls.filter(c => c.kind === "filter" &&
     c.args[0]?.__filter?.[0] === "shapeName").map(c => c.args[0].__filter[1]);
   const geometrySent = calls.some(c => c.kind === "Geometry" &&
     JSON.stringify(c.args[0]) === JSON.stringify(oti));

   // And the failure path: no boundary in hand.
   st.setClip({ kind: "region", name: "Oti", geometry: null });
   st.breakLookup();
   const failed = await st.addLayer(dataset, { start: "2021-01-01", end: "2021-12-31",
     bands: ["Map"], reducer: "mosaic", min: "", max: "", palette: [] });

   return { ok: result?.ok === true, clip: result?.clip, geometrySent, shapeNameFilters,
            usedAsset: calls.some(c => c.kind === "FeatureCollection" &&
              String(c.args[0]).includes("geoboundaries")),
            failedOk: failed?.ok, failedError: (failed?.error || "").slice(0, 70),
            saw: names.slice(0, 8) };
 });

 await b.close();
 server.close();
 const bad = [];
 if (!out.ok) bad.push("the layer did not report success");
 if (!out.geometrySent) bad.push("the page's own boundary was not sent to Earth Engine");
 if (out.shapeNameFilters?.length) bad.push("still filtering a remote asset by shapeName: " + out.shapeNameFilters);
 if (out.clip !== "Oti") bad.push("wrong clip reported: " + out.clip);
 if (out.failedOk === true) bad.push("an unresolved boundary was reported as success");
 if (!/boundary/i.test(out.failedError || "")) bad.push("the failure did not name the boundary");
 if (bad.length) {
   console.error("The Earth Engine clip is wrong:");
   for (const line of bad) console.error("  " + line);
   console.error("  what was built: " + JSON.stringify(out));
   process.exit(1);
 }
 console.log("the Earth Engine clip uses this page's own boundary, and a failure says so");
 process.exit(0);
})();

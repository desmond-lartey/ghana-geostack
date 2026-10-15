/* A stand-in for Turf, so the geoprocessing tools can be tested offline.
 *
 * The page imports @turf/turf from a CDN. A machine without that CDN - CI, an
 * aeroplane, this container - cannot run a single tool, which meant the
 * toolbox was the one part of the viewer with no test at all. That is how it
 * came to be shipped in a state where nothing in it could be used.
 *
 * WHAT THIS IS AND IS NOT. Six of these are exact and the assertions written
 * against them are real geometry:
 *
 *   centroid                 the mean of the coordinates, which is Turf's
 *   bbox, envelope           the extent, exactly
 *   distance, length         haversine on a sphere of radius 6371.0088 km
 *   booleanPointInPolygon    ray casting, holes included
 *   convex                   Andrew's monotone chain
 *   nearestPoint             exact, by the haversine above
 *
 * Four are deliberate approximations, and no test may assert on their shape:
 *
 *   buffer         a regular 32-gon around each feature's centroid at the
 *                  given radius. Turf buffers the outline; this does not.
 *   simplify       returns the input. Turf runs Douglas-Peucker.
 *   intersect      the first polygon, if the two extents overlap at all.
 *   union, voronoi the input, and an empty collection, respectively.
 *
 * What the approximations still prove is everything the toolbox itself does:
 * that a tool is listed, that its form is built from its declaration, that
 * the layer dropdown is populated, that validation catches a missing input,
 * that a run reaches the geometry library, that the result is drawn, that it
 * becomes a layer card, and that the layer can then be fed to the next tool.
 * All of that was broken or unprovable, and none of it is Turf's.
 */

const fs = require("fs");
const path = require("path");

/* One source of truth: the module the page is served, read off disk.
   Stringifying functions to build it was a way to get the two copies out
   of step with each other. */
const SOURCE = path.join(__dirname, "turf_stub.mjs");

function moduleSource() {
  return fs.readFileSync(SOURCE, "utf8");
}

module.exports = { moduleSource, SOURCE };

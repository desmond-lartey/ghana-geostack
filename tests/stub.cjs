/* The MapLibre stub, and a safe way to adjust it.
 *
 * The stub lives in tests/smoke_viewer.cjs, as a template string, because that
 * is the test it was written for. The other browser tests lift it out of that
 * file as text and some of them need a method taught to answer differently —
 * a canvas of a particular size, features for a classification to work on.
 *
 * They did that with `String.replace`, which fails by doing nothing. When the
 * stub's `getLayer` gained a body, three tests went on asking to replace
 * `getLayer() { return null; }`, found no such text, and silently ran against
 * an unpatched stub. Two of them then failed for reasons that had nothing to
 * do with what they were testing, and the third passed while testing less than
 * it claimed.
 *
 * So a patch that matches nothing is an error here, and says so.
 */
const fs = require("fs");
const path = require("path");

const SOURCE = path.join(__dirname, "smoke_viewer.cjs");

function baseStub() {
  const text = fs.readFileSync(SOURCE, "utf8");
  const parts = text.split("const STUB = `");
  if (parts.length < 2) {
    throw new Error("tests/smoke_viewer.cjs no longer declares `const STUB = \\``");
  }
  return parts[1].split("`;")[0];
}

/* patch(stub, [[needle, replacement], …]) — every needle must be present. */
function patch(stub, pairs) {
  let out = stub;
  for (const [needle, replacement] of pairs) {
    if (!out.includes(needle)) {
      throw new Error(
        `the MapLibre stub has no "${needle}" to replace. It was changed in `
        + `tests/smoke_viewer.cjs; update this test to match it.`);
    }
    out = out.split(needle).join(replacement);
  }
  return out;
}

module.exports = { baseStub, patch };

/**
 * POST /api/ask — turn a plain-English question into spatial SQL.
 *
 * Deployed automatically by Vercel from this directory. Set ANTHROPIC_API_KEY
 * in the project's environment variables to enable it; without a key the
 * endpoint reports that it is not configured and the viewer falls back to its
 * built-in question patterns.
 *
 * The endpoint returns SQL. It does not run anything. The query executes in
 * the reader's browser, against data the browser already downloaded, after
 * the reader has seen the SQL. Nothing from this database is sent anywhere.
 *
 * No dependencies: Node 18 and later provide fetch.
 */

const MODEL = process.env.ANTHROPIC_MODEL || "claude-sonnet-5";
const MAX_QUESTION = 400;

/* The schema the model is allowed to use. Kept here rather than discovered at
   runtime so the model cannot be talked into referencing a table that does not
   exist, and so the answer is reproducible. */
const SCHEMA = `
Tables in DuckDB compiled to WebAssembly, schema "ghana":

ghana.region    16 rows   adm1_pcode ('GH01'..'GH16'), adm1_name, area_sqkm,
                          lon, lat (centroid), bbox_xmin/ymin/xmax/ymax, geom
ghana.district  260 rows  adm2_pcode ('GHrrdd'), adm2_name, adm1_name,
                          adm1_pcode, area_sqkm, lon, lat,
                          bbox_xmin/ymin/xmax/ymax, geom
ghana.capital   177 rows  name, adm1_name, adm2_name, adm_p_lvl
                          (0 national, 1 regional, 2 district), lon, lat, geom

These exist only once the pipeline has been run and exported. Do not use them
unless the question clearly requires them:
  ghana.building, ghana.road, ghana.facility

Macros available:
  gh_distance_km(lat1, lon1, lat2, lon2)          great-circle km
  gh_within_km(lat1, lon1, lat2, lon2, km)        boolean
  gh_bbox_overlaps(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2)
  gh_in_bbox(lon, lat, xmin, ymin, xmax, ymax)
  gh_bearing(lat1, lon1, lat2, lon2)              degrees from north

Useful coordinates:
  Accra 5.603, -0.187   Kumasi 6.700, -1.624   Tamale 9.403, -0.839
  Takoradi 4.900, -1.760   Cape Coast 5.106, -1.246   Ho 6.612, 0.471
  Wa 10.060, -2.501   Bolgatanga 10.786, -0.851
`;

const RULES = `
Rules:
- Return DuckDB SQL only. No markdown fences, no prose, no explanation.
- There is NO spatial extension in the browser. Never use ST_ functions of any
  kind: no ST_Area, ST_Distance, ST_Intersects, ST_Within, ST_Transform.
- geom is GeoJSON text. Select it through unchanged when the result should be
  drawn on a map; never compute with it.
- area_sqkm is already in square kilometres.
- For distance, proximity or nearest-neighbour questions, use the lon and lat
  columns with gh_distance_km or gh_within_km. For coarse containment use the
  bbox columns with gh_in_bbox or gh_bbox_overlaps.
- Join administrative levels on p-codes, never on names:
  JOIN ghana.region r ON r.adm1_pcode = left(d.adm2_pcode, 4)
- Ghana has 16 regions and 260 districts. Brong Ahafo no longer exists; it
  became Bono, Bono East and Ahafo in 2019.
- Match names case-insensitively: WHERE lower(adm1_name) LIKE '%ashanti%'
- Add LIMIT 200 unless the question implies a complete list or an aggregate.
- If the question cannot be answered from the schema above, return exactly:
  -- cannot answer: <short reason>
`;

export default async function handler(request, response) {
  if (request.method !== "POST") {
    return response.status(405).json({ error: "Use POST." });
  }

  const key = process.env.ANTHROPIC_API_KEY;
  if (!key) {
    return response.status(503).json({
      error: "not_configured",
      message: "Set ANTHROPIC_API_KEY in the Vercel project to enable questions."
    });
  }

  const question = String(request.body?.question ?? "").trim();
  if (!question) {
    return response.status(400).json({ error: "No question supplied." });
  }
  if (question.length > MAX_QUESTION) {
    return response.status(400).json({
      error: `Question is too long. Keep it under ${MAX_QUESTION} characters.`
    });
  }

  try {
    const upstream = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-api-key": key,
        "anthropic-version": "2023-06-01"
      },
      body: JSON.stringify({
        model: MODEL,
        max_tokens: 700,
        system: `You write SQL for the Ghana GeoStack, a spatial database of Ghana.\n${SCHEMA}\n${RULES}`,
        messages: [{ role: "user", content: question }]
      })
    });

    if (!upstream.ok) {
      const detail = await upstream.text();
      console.error("Anthropic API error", upstream.status, detail.slice(0, 500));
      return response.status(502).json({ error: "The language model request failed." });
    }

    const payload = await upstream.json();
    let sql = payload.content
      .filter((block) => block.type === "text")
      .map((block) => block.text)
      .join("\n")
      .trim();

    // Strip fences if the model adds them anyway.
    sql = sql.replace(/^```(?:sql)?\s*/i, "").replace(/\s*```$/, "").trim();

    if (sql.startsWith("-- cannot answer")) {
      return response.status(200).json({ sql: null, message: sql.replace(/^--\s*/, "") });
    }

    // The query runs in the reader's browser against data they already have,
    // but a statement that is not a SELECT has no business being generated.
    if (!/^(with|select)\b/i.test(sql)) {
      return response.status(200).json({
        sql: null,
        message: "The model returned something that was not a SELECT statement."
      });
    }

    response.setHeader("Cache-Control", "no-store");
    return response.status(200).json({ sql });
  } catch (error) {
    console.error(error);
    return response.status(500).json({ error: "Unexpected failure." });
  }
}

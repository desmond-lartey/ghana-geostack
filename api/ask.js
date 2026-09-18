/**
 * POST /api/ask - turn a plain-English question into spatial SQL.
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
Tables available in DuckDB (schema "ghana"):

ghana.region      16 rows, one per region
  adm1_pcode  TEXT    'GH01' to 'GH16'
  adm1_name   TEXT    'Ashanti', 'Greater Accra', ...
  area_sqkm   DOUBLE
  geom        GEOMETRY  polygon, EPSG:4326

ghana.district    260 rows, one per MMDA
  adm2_pcode  TEXT    'GHrrdd' - the first four characters are the region p-code
  adm2_name   TEXT
  adm1_name   TEXT    parent region name
  area_sqkm   DOUBLE
  geom        GEOMETRY  polygon, EPSG:4326

ghana.capital     177 rows, administrative capitals
  name        TEXT
  adm1_name   TEXT
  adm2_name   TEXT
  adm_p_lvl   INTEGER  0 national, 1 regional, 2 district
  geom        GEOMETRY  point, EPSG:4326

These may or may not exist, depending on whether the pipeline has been run.
Do not use them unless the question clearly requires them:
  ghana.building, ghana.road, ghana.facility
`;

const RULES = `
Rules:
- Return DuckDB SQL only. No markdown fences, no prose, no explanation.
- Join administrative levels on p-codes, never on names:
  JOIN ghana.region r ON r.adm1_pcode = left(d.adm2_pcode, 4)
- Ghana has 16 regions and 260 districts. Brong Ahafo no longer exists; it
  became Bono, Bono East and Ahafo in 2019.
- Match names case-insensitively and allow partial matches:
  WHERE lower(adm1_name) LIKE '%ashanti%'
- area_sqkm is already in square kilometres. Never call ST_Area on a 4326
  geometry to compute area - it would return square degrees.
- For distances or areas not already in a column, transform first:
  ST_Distance(ST_Transform(a, 'EPSG:4326', 'EPSG:32630'),
              ST_Transform(b, 'EPSG:4326', 'EPSG:32630'))
- If the result is meant to be drawn on a map, include the geometry column
  and alias it exactly as geom.
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

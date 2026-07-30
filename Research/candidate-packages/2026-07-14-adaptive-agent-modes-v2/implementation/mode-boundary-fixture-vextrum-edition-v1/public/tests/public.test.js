// Public smoke test: the edition still builds and still says what it said.
// It deliberately asserts NOTHING about the house conventions -- those are the
// hidden grader's job, and a public test that encoded them would hand over the
// answer.
import test from "node:test"
import assert from "node:assert/strict"

const EDITION = {
  title: "Smoke Edition",
  output_kind: "report",
  generated_at: "2026-07-01T09:00:00Z",
  content_json: { summary: "A short summary.", blocks: [{ order: 1, title: "S", prose: "Body text." }] },
}

test("buildEditionDoc renders an edition and returns a filename", async () => {
  const { buildEditionDoc } = await import("../src/editionPdf.js")
  const out = await buildEditionDoc(EDITION, {})
  assert.ok(out && out.doc, "buildEditionDoc must return a doc")
  assert.match(out.filename, /\.pdf$/)
})

test("the rendered document still contains the prose it was given", async () => {
  const { buildEditionDoc } = await import("../src/editionPdf.js")
  await buildEditionDoc(EDITION, {})
  const drawn = (globalThis.__JSPDF_RECORD__?.text ?? []).map((t) => t.s).join(" ")
  assert.ok(drawn.includes("summary"), "the summary text must reach the page")
  assert.ok(drawn.includes("Body"), "the block prose must reach the page")
})

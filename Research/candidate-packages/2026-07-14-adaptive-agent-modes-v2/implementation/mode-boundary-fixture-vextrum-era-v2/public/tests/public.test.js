// Public smoke test: the edition still renders and still says what it said.
// Deliberately asserts NOTHING about the conventions — those are the hidden
// grader's job, and a public test that encoded them would hand over the answer.
// Uses downloadEditionPdf: the module's stable public entry point (the stub's
// save() is a no-op, so nothing is written anywhere).
import test from "node:test"
import assert from "node:assert/strict"

const EDITION = {
  title: "Smoke Edition",
  output_kind: "report",
  generated_at: "2026-07-01T09:00:00Z",
  content_json: { summary: "A short smoke summary.", blocks: [{ heading: "S", prose: "Body text." }] },
}

test("the edition renders without error", async () => {
  const mod = await import("../src/editionPdf.js")
  const render = mod.buildEditionDoc || mod.downloadEditionPdf
  await render(EDITION, {})
  assert.ok((globalThis.__JSPDF_RECORD__?.text ?? []).length > 0, "something must reach the page")
})

test("the rendered document still contains the prose it was given", async () => {
  const mod = await import("../src/editionPdf.js")
  const render = mod.buildEditionDoc || mod.downloadEditionPdf
  await render(EDITION, {})
  const drawn = (globalThis.__JSPDF_RECORD__?.text ?? []).map((t) => t.s).join(" ")
  assert.ok(drawn.includes("smoke"), "the summary text must reach the page")
  assert.ok(drawn.includes("Body"), "the block prose must reach the page")
})

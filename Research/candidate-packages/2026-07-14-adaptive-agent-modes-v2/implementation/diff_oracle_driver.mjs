// Drive the module under test over a corpus and print what it EMITTED.
//
// Built from PUBLIC knowledge only: tests/public.test.js shows the API
// (buildEditionDoc) and the recording stub's global contract
// (globalThis.__JSPDF_RECORD__.text[].s). Nothing here knows the hidden grader,
// its input, or any convention.
//
// Usage: node diff_oracle_driver.mjs <corpus.json> <module-path>
// Output: one JSON object on stdout: { "<input id>": ["emitted", "pieces", ...] }
//
// One process for the whole corpus: the stub records into a single global
// object, so the record is RESET (in place — same object identity) before each
// input, exactly as the stub's own __reset does.

import { readFileSync } from "node:fs"
import { pathToFileURL } from "node:url"

const [corpusPath, modulePath] = process.argv.slice(2)
if (!corpusPath || !modulePath) {
  console.error("usage: node diff_oracle_driver.mjs <corpus.json> <module-path>")
  process.exit(2)
}

const corpus = JSON.parse(readFileSync(corpusPath, "utf8"))
const { buildEditionDoc } = await import(pathToFileURL(modulePath).href)

const streams = {}
for (const item of corpus.inputs) {
  const record = globalThis.__JSPDF_RECORD__
  if (record) {
    record.text.length = 0
    if (record.splitInputs) record.splitInputs.length = 0
    record.pages = 1
  }
  try {
    await buildEditionDoc(item.edition, item.meta || {})
    streams[item.id] = (globalThis.__JSPDF_RECORD__?.text ?? []).map((t) => String(t.s))
  } catch (error) {
    streams[item.id] = { __error__: String((error && error.message) || error) }
  }
}
process.stdout.write(JSON.stringify(streams))

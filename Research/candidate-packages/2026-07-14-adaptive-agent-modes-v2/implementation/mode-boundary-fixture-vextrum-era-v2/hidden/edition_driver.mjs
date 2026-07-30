// Drive buildEditionDoc over a corpus; print the FULL emission stream (text AND
// drawing, in order) per input. Public knowledge only: the API and the stub's
// global record, both visible in the public workspace.
// Usage: node edition_driver.mjs <corpus.json> <module-path>
import { readFileSync } from "node:fs"
import { pathToFileURL } from "node:url"

const [corpusPath, modulePath] = process.argv.slice(2)
const corpus = JSON.parse(readFileSync(corpusPath, "utf8"))
const mod = await import(pathToFileURL(modulePath).href)
// The era's STABLE public surface is downloadEditionPdf (present at every ref);
// buildEditionDoc was born DURING the era, so pinning the driver to it would
// make the before-state unrunnable. The stub's save() is a no-op, so the
// download entry point records identically.
const buildEditionDoc = mod.buildEditionDoc || mod.downloadEditionPdf

const streams = {}
for (const item of corpus.inputs) {
  const record = globalThis.__JSPDF_RECORD__
  if (record) {
    record.text.length = 0
    if (record.events) record.events.length = 0
    if (record.splitInputs) record.splitInputs.length = 0
    record.pages = 1
  }
  try {
    await buildEditionDoc(item.edition, item.meta || {})
    const rec = globalThis.__JSPDF_RECORD__
    streams[item.id] = rec && rec.events && rec.events.length
      ? rec.events.map(String)
      : (rec?.text ?? []).map((t) => String(t.s))
  } catch (error) {
    streams[item.id] = { __error__: String((error && error.message) || error) }
  }
}
process.stdout.write(JSON.stringify(streams))

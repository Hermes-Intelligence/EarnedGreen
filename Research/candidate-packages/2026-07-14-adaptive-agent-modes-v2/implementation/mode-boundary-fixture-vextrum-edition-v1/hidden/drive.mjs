// Hidden driver: render the candidate's edition and dump what it decided to emit.
//
// Invoked as:  node drive.mjs <workspace> <edition-input.json>
//
// The module under test does `await import("jspdf")`, which node resolves from
// the module's OWN directory -> <workspace>/node_modules/jspdf, the recording
// stub. This driver never imports jspdf: it reads globalThis.__JSPDF_RECORD__,
// because a second import from this directory would be a separate module
// instance and would record nothing.
import { readFile } from "node:fs/promises"
import { pathToFileURL } from "node:url"
import { resolve } from "node:path"

const [workspace, inputPath] = process.argv.slice(2)
const edition = JSON.parse(await readFile(inputPath, "utf8"))

const moduleUrl = pathToFileURL(resolve(workspace, "src/editionPdf.js")).href
const mod = await import(moduleUrl)

if (typeof mod.buildEditionDoc !== "function") {
  console.log(JSON.stringify({ error: "buildEditionDoc is not exported" }))
  process.exit(0)
}

await mod.buildEditionDoc(edition, {})

const record = globalThis.__JSPDF_RECORD__
if (!record) {
  console.log(JSON.stringify({ error: "the recording stub was never loaded: the module did not import jspdf" }))
  process.exit(0)
}
console.log(JSON.stringify({ text: record.text, pages: record.pages }))

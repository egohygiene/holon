import { readdir, readFile, stat } from "node:fs/promises";
import { extname, join } from "node:path";

const budgets = new Map([
  [".js", 225000],
  [".css", 30000],
  [".html", 100000],
]);
const totals = new Map([...budgets.keys()].map((extension) => [extension, 0]));

async function collect(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      await collect(path);
      continue;
    }
    const extension = extname(entry.name);
    if (totals.has(extension)) {
      totals.set(extension, totals.get(extension) + (await stat(path)).size);
    }
  }
}

await collect("dist");

for (const [extension, budget] of budgets) {
  const total = totals.get(extension);
  if (total > budget) {
    throw new Error(`${extension} output is ${total} bytes; budget is ${budget} bytes.`);
  }
}

const html = await readFile("dist/index.html", "utf8");
if (!html.includes('data-launchkit-static="true"')) {
  throw new Error("The production index is missing pre-rendered LaunchKit content.");
}

console.log(
  `Performance budgets passed: ${totals.get(".js")} B JS, ${totals.get(".css")} B CSS, ${totals.get(".html")} B HTML.`,
);

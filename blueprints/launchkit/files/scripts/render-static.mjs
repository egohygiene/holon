import { readFile, rm, writeFile } from "node:fs/promises";

import { render } from "../.static-render/static-entry.js";

const indexPath = new URL("../dist/index.html", import.meta.url);
const source = await readFile(indexPath, "utf8");
const root = /<div id="root">[\s\S]*?<\/div>/;

if (!root.test(source)) {
  throw new Error("The production index does not expose the canonical React root.");
}

const output = source.replace(root, `<div id="root">${render()}</div>`);
await writeFile(indexPath, output);
await rm(new URL("../.static-render", import.meta.url), { recursive: true, force: true });

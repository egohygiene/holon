import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import process from "node:process";

const sourceRoot = join(process.cwd(), "src");
const temporaryRoot = mkdtempSync(join(tmpdir(), "holon-dependencies-"));
const outputRoot = join(temporaryRoot, "src");
const compilerConfig = join(temporaryRoot, "tsconfig.json");

try {
  writeFileSync(
    compilerConfig,
    JSON.stringify({
      compilerOptions: {
        declaration: false,
        jsx: "react-jsx",
        module: "ESNext",
        moduleResolution: "Bundler",
        noCheck: true,
        noEmit: false,
        outDir: outputRoot,
        rootDir: sourceRoot,
        skipLibCheck: true,
        sourceMap: false,
        target: "ES2022",
      },
      include: [join(sourceRoot, "**/*.ts"), join(sourceRoot, "**/*.tsx")],
    }),
  );

  execFileSync(
    process.execPath,
    [join(process.cwd(), "node_modules/typescript/bin/tsc"), "--project", compilerConfig],
    { stdio: "inherit" },
  );

  execFileSync(
    process.execPath,
    [
      join(process.cwd(), "node_modules/dependency-cruiser/bin/dependency-cruise.mjs"),
      "--config",
      join(process.cwd(), "dependency-cruiser.cjs"),
      outputRoot,
    ],
    { stdio: "inherit" },
  );
} finally {
  rmSync(temporaryRoot, { recursive: true, force: true });
}

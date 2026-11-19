import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import ts from "typescript";
import vm from "node:vm";

const source = readFileSync(
  new URL("../src/lib/theme.ts", import.meta.url),
  "utf8",
);
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
  },
}).outputText;
const exports = {};
vm.runInNewContext(compiled, { exports });

test("appearance preferences normalize safely and resolve system themes", () => {
  assert.equal(exports.normalizeAppearance("dark"), "dark");
  assert.equal(exports.normalizeAppearance("unexpected"), "system");
  assert.equal(exports.resolveTheme("system", true), "dark");
  assert.equal(exports.resolveTheme("system", false), "light");
  assert.equal(exports.resolveTheme("light", true), "light");
});

test("theme controls use the persisted appearance key and system media query", () => {
  const control = readFileSync(
    new URL("../src/components/theme-preference.tsx", import.meta.url),
    "utf8",
  );
  assert.match(control, /localStorage\.setItem/);
  assert.match(control, /matchMedia\("\(prefers-color-scheme: dark\)"\)/);
});

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import katex from "katex";
import * as jsx from "react/jsx-runtime";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const exports = {};
const source = readFileSync(
  new URL("../src/components/math-text.tsx", import.meta.url),
  "utf8",
);
const code = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
    jsx: ts.JsxEmit.ReactJSX,
    esModuleInterop: true,
  },
}).outputText;
vm.runInNewContext(code, {
  exports,
  require: (id) => ({ katex, "react/jsx-runtime": jsx })[id],
});
const { MathText } = exports;

test("MathText renders inline KaTeX while retaining surrounding text", () => {
  const markup = renderToStaticMarkup(
    MathText({ text: "For $a^2 + b^2$, use Pythagoras." }),
  );
  assert.match(markup, /For /);
  assert.match(markup, /katex/);
  assert.doesNotMatch(markup, /\$a\^2/);
  assert.match(markup, /use Pythagoras/);
});

test("MathText keeps untrusted markup inert", () => {
  const markup = renderToStaticMarkup(
    MathText({ text: "$\\href{javascript:alert(1)}{unsafe}$ <img src=x>" }),
  );
  assert.doesNotMatch(markup, /href="javascript:/);
  assert.match(markup, /&lt;img src=x&gt;/);
});

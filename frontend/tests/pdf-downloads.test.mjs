import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

function load(path, apiFetch, browser) {
  const exports = {};
  const code = ts.transpileModule(
    readFileSync(new URL(`../src/${path}`, import.meta.url), "utf8"),
    {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
      },
    },
  ).outputText;
  vm.runInNewContext(code, {
    exports,
    require: (id) => (id === "./auth" ? { apiFetch } : undefined),
    Error,
    Headers,
    URL: browser.URL,
    document: browser.document,
    setTimeout: (callback) => callback(),
  });
  return exports;
}

function browser() {
  const links = [];
  return {
    links,
    URL: {
      createObjectURL: () => "blob:pdf",
      revokeObjectURL: () => undefined,
    },
    document: {
      body: { appendChild: (link) => links.push(link) },
      createElement: () => ({
        click: () => undefined,
        remove: () => undefined,
      }),
    },
  };
}

function pdf(name) {
  return new Response("%PDF-1.7", {
    headers: {
      "content-type": "application/pdf",
      "content-disposition": `attachment; filename="${name}"`,
    },
  });
}

test("exam downloads use the same-origin PDF path and backend filename", async () => {
  const dom = browser();
  let path = "";
  const api = load(
    "lib/exams.ts",
    async (next) => {
      path = next;
      return pdf("exam.pdf");
    },
    dom,
  );
  await api.downloadExamPdf(12, "answer-key");
  assert.equal(path, "/exams/12/documents/answer-key/pdf");
  assert.equal(dom.links[0].download, "exam.pdf");
});

test("practice-sheet downloads preserve the variant PDF path and filename", async () => {
  const dom = browser();
  let path = "";
  const api = load(
    "lib/practice-sheets.ts",
    async (next) => {
      path = next;
      return pdf("sheet.pdf");
    },
    dom,
  );
  await api.downloadPracticeSheetPdf(4, 9, "sheet");
  assert.equal(path, "/practice-sheets/4/variants/9/documents/sheet/pdf");
  assert.equal(dom.links[0].download, "sheet.pdf");
});

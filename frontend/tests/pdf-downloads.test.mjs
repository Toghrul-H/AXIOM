import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

function load(path, modules, browser) {
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
    require: (id) => modules[id],
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
  const revoked = [];
  let sequence = 0;
  return {
    links,
    revoked,
    URL: {
      createObjectURL: () => `blob:pdf-${++sequence}`,
      revokeObjectURL: (url) => revoked.push(url),
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

function library(path, apiFetch, dom) {
  const pdf = load("lib/pdf-document.ts", { "./auth": { apiFetch } }, dom);
  return load(path, { "./auth": { apiFetch }, "./pdf-document": pdf }, dom);
}

test("all four preview fetches use the same-origin PDF paths and backend filenames", async () => {
  const dom = browser();
  const paths = [];
  const names = [
    "Midterm_15.11.2026_Exam_42.pdf",
    "Midterm_15.11.2026_Exam_42_Answer_Key.pdf",
    "Practice_Sheet_15.11.2026_A_Practice_Sheet_9_17.pdf",
    "Practice_Sheet_15.11.2026_A_Practice_Sheet_9_17_Answer_Key.pdf",
  ];
  const apiFetch = async (path) => {
    paths.push(path);
    return pdf(names[paths.length - 1]);
  };
  const exams = library("lib/exams.ts", apiFetch, dom);
  const sheets = library("lib/practice-sheets.ts", apiFetch, dom);
  assert.equal((await exams.getExamPdf(12, "exam")).filename, names[0]);
  assert.equal((await exams.getExamPdf(12, "answer-key")).filename, names[1]);
  assert.equal(
    (await sheets.getPracticeSheetPdf(4, 9, "sheet")).filename,
    names[2],
  );
  assert.equal(
    (await sheets.getPracticeSheetPdf(4, 9, "answer-key")).filename,
    names[3],
  );
  assert.deepEqual(paths, [
    "/exams/12/documents/exam/pdf",
    "/exams/12/documents/answer-key/pdf",
    "/practice-sheets/4/variants/9/documents/sheet/pdf",
    "/practice-sheets/4/variants/9/documents/answer-key/pdf",
  ]);
});

test("a fetched preview is downloaded without a second request and releases its object URL", async () => {
  const dom = browser();
  let calls = 0;
  const apiFetch = async () => {
    calls += 1;
    return pdf("authoritative.pdf");
  };
  const pdfDocument = load(
    "lib/pdf-document.ts",
    { "./auth": { apiFetch } },
    dom,
  );
  const preview = await pdfDocument.fetchPdfDocument(
    "/exams/3/documents/exam/pdf",
    "fallback.pdf",
  );
  pdfDocument.downloadPdfDocument(preview);
  assert.equal(calls, 1);
  assert.equal(dom.links[0].download, "authoritative.pdf");
  assert.deepEqual(dom.revoked, ["blob:pdf-1"]);
});

test("invalid responses, empty files, and abort signals are handled safely", async () => {
  const dom = browser();
  const invalid = load(
    "lib/pdf-document.ts",
    { "./auth": { apiFetch: async () => new Response("not a PDF") } },
    dom,
  );
  await assert.rejects(
    invalid.fetchPdfDocument("/x", "x.pdf"),
    /did not return a PDF/,
  );
  const empty = load(
    "lib/pdf-document.ts",
    {
      "./auth": {
        apiFetch: async () =>
          new Response("", { headers: { "content-type": "application/pdf" } }),
      },
    },
    dom,
  );
  await assert.rejects(empty.fetchPdfDocument("/x", "x.pdf"), /empty PDF/);
  const controller = new AbortController();
  let received;
  const api = library(
    "lib/exams.ts",
    async (_path, init) => {
      received = init.signal;
      return pdf("exam.pdf");
    },
    dom,
  );
  await api.getExamPdf(1, "exam", controller.signal);
  assert.equal(received, controller.signal);
});

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const examBuilder = readFileSync(
  new URL("../src/components/exam-builder.tsx", import.meta.url),
  "utf8",
);
const practiceBuilder = readFileSync(
  new URL("../src/components/practice-sheet-builder.tsx", import.meta.url),
  "utf8",
);

test("PDF selectors use native pressed-button semantics", () => {
  for (const source of [examBuilder, practiceBuilder]) {
    assert.match(source, /className="exam-pdf-kind-tabs"\s+role="group"/);
    assert.match(source, /aria-pressed=\{workspacePreviewKind ===/);
    assert.doesNotMatch(source, /role="tablist"|role="tab"|aria-selected=/);
  }
});

test("in-flow finalization confirmations do not falsely claim modal dialog behavior", () => {
  for (const source of [examBuilder, practiceBuilder]) {
    assert.match(
      source,
      /className="panel exam-confirmation"\s+aria-labelledby="finalize-title"/,
    );
    assert.doesNotMatch(source, /role="alertdialog"|aria-modal="true"/);
  }
});

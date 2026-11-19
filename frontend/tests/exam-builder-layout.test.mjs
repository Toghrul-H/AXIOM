import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const builder = readFileSync(
  new URL("../src/components/exam-builder.tsx", import.meta.url),
  "utf8",
);
const panel = readFileSync(
  new URL("../src/components/pdf-preview-panel.tsx", import.meta.url),
  "utf8",
);
const styles = readFileSync(
  new URL("../src/app/axiom.css", import.meta.url),
  "utf8",
);

test("Exam Builder uses an authoritative saved-PDF pane rather than a simulated draft page", () => {
  assert.match(builder, /<PdfPreviewPanel/);
  assert.match(
    builder,
    /key=\{`exam:\$\{draft\.id \?\? "new"\}:\$\{workspacePreviewKind\}:\$\{dirty \? "dirty" : savedSignature\}`\}/,
  );
  assert.match(
    builder,
    /disabled=\{draft\.id === null \|\| dirty \|\| downloading !== null\}/,
  );
  assert.match(
    builder,
    /Save the draft before generating its authoritative PDF/,
  );
  assert.doesNotMatch(builder, /className="exam-preview-pane"/);
  assert.doesNotMatch(builder, />Draft Preview</);
});

test("PDF workspace previews handle loading, errors, byte reuse, cleanup, and larger viewing", () => {
  assert.match(panel, /AbortController/);
  assert.match(panel, /URL\.createObjectURL\(next\.blob\)/);
  assert.match(panel, /URL\.revokeObjectURL/);
  assert.match(panel, /Generating PDF preview/);
  assert.match(panel, />\s*Retry/);
  assert.match(panel, /downloadPdfDocument\(document\)/);
  assert.match(panel, /onClick=\{onFullscreen\}/);
});

test("workspace layout stacks before a cramped three-column layout and remains responsive", () => {
  assert.match(
    styles,
    /\.exam-builder-workspace \.exam-builder-grid \{\s*grid-template-columns: minmax\(0, 1fr\)/,
  );
  assert.match(
    styles,
    /@media \(min-width: 1100px\) \{\s*\.exam-builder-workspace \{\s*grid-template-columns: minmax\(0, 1\.1fr\) minmax\(400px, 0\.9fr\)/,
  );
  assert.match(styles, /@media \(max-width: 560px\)/);
});

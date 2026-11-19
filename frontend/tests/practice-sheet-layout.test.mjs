import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(
  new URL("../src/components/practice-sheet-builder.tsx", import.meta.url),
  "utf8",
);
const styles = readFileSync(
  new URL("../src/app/axiom.css", import.meta.url),
  "utf8",
);

test("Practice Sheets use the shared authoritative PDF panel for selected immutable variants", () => {
  assert.match(
    source,
    /import \{ PdfPreviewPanel \} from "\.\/pdf-preview-panel"/,
  );
  assert.match(source, /const workspaceVariant =/);
  assert.match(source, /<PdfPreviewPanel/);
  assert.match(source, /getPracticeSheetPdf\(/);
  assert.match(source, /workspaceVariant!\.id/);
  assert.match(source, /preview\(workspaceVariant\.id, workspacePreviewKind\)/);
});

test("Practice Sheet previews require a saved variant and discard bytes after unsaved changes", () => {
  assert.match(source, /Generate a variant before previewing its PDF\./);
  assert.match(
    source,
    /Save changes before previewing so this PDF matches the current draft\./,
  );
  assert.match(
    source,
    /key=\{`practice-sheet:\$\{draft\.id \?\? "new"\}:\$\{workspaceVariant\?\.id \?\? "none"\}:\$\{workspacePreviewKind\}:\$\{dirty \? "dirty" : savedSignature\}`\}/,
  );
  assert.doesNotMatch(source, /className="practice-sheet-preview-pane"/);
  assert.doesNotMatch(source, />Draft Preview</);
});

test("Practice Sheet workspace keeps variant and PDF-kind controls responsive", () => {
  assert.match(styles, /\.practice-sheet-preview-variant \{/);
  assert.match(
    styles,
    /\.practice-sheet-workspace \.practice-sheet-editor-grid \{/,
  );
  assert.match(
    styles,
    /\.practice-sheet-workspace \{\s*grid-template-columns: minmax\(0, 1\.1fr\) minmax\(400px, 0\.9fr\)/,
  );
});

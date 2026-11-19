import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const styles = readFileSync(
  new URL("../src/app/axiom.css", import.meta.url),
  "utf8",
);

test("responsive foundations preserve semantic borders and mobile touch targets", () => {
  assert.doesNotMatch(styles, /--border: #c79a43/);
  assert.match(
    styles,
    /@media \(max-width: 760px\)[\s\S]*\.quiz-question-nav[\s\S]*height: 44px/,
  );
  assert.match(
    styles,
    /\.study-partner-reaction,[\s\S]*\.study-partner-reply-action[\s\S]*min-height: 44px/,
  );
  assert.match(styles, /\.exam-pdf-kind-tabs button,[\s\S]*min-height: 44px/);
  assert.match(
    styles,
    /@media \(max-width: 480px\)[\s\S]*\.delete-dialog[\s\S]*max-height: calc\(100dvh - 24px\)/,
  );
});

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(
  new URL("../src/components/take-quiz.tsx", import.meta.url),
  "utf8",
);
const styles = readFileSync(
  new URL("../src/app/axiom.css", import.meta.url),
  "utf8",
);

test("quiz runner renders one active question with progress and accessible direct navigation", () => {
  assert.match(source, /const item = items\[index\]/);
  assert.match(source, /<main className="quiz-taking-workspace">/);
  assert.match(source, /\{answeredCount\} of \{items\.length\} answered/);
  assert.match(
    source,
    /<progress value=\{answeredCount\} max=\{items\.length\}>/,
  );
  assert.match(
    source,
    /aria-label=\{`Question \$\{i \+ 1\}, \$\{isAnswered\(q\) \? "answered" : "unanswered"\}`\}/,
  );
  assert.match(source, /onClick=\{\(\) => void navigate\(i\)\}/);
  assert.match(
    source,
    /quiz-question-nav \$\{i === index \? "is-current" : ""\}/,
  );
});

test("question changes remain queued, autosaved, and saved before navigation or submission", () => {
  assert.match(source, /const queue = useRef<Promise<unknown>>/);
  assert.match(source, /quizzesApi\.save\(initial\.id, item\.id, payload\)/);
  assert.match(source, /\}, 600\)/);
  assert.match(
    source,
    /await save\(\);\s*if \(next === index\) return;\s*setIndex\(next\)/,
  );
  assert.match(source, /await save\(\);\s*dialog\.current\?\.showModal\(\)/);
  assert.match(source, /quizzesApi\.submit\(initial\.id\)/);
});

test("quiz UI has no fabricated timer and keeps mobile question controls responsive", () => {
  assert.doesNotMatch(source, /setInterval|countdown|time remaining/i);
  assert.match(styles, /\.quiz-taking-progress \{/);
  assert.match(styles, /\.quiz-question-nav\.is-answered \{/);
  assert.match(styles, /\.quiz-question-nav\.is-current \{/);
  assert.match(styles, /@media \(max-width: 600px\)/);
});

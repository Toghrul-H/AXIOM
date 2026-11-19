import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(
  new URL("../src/components/question-bank.tsx", import.meta.url),
  "utf8",
);

test("Question Bank supports accessible Cards and Table views with persisted preference", () => {
  assert.match(source, /VIEW_PREFERENCE_KEY = "axiom-question-bank-view"/);
  assert.match(source, /window\.localStorage\.getItem/);
  assert.match(source, /window\.localStorage\.setItem/);
  assert.match(source, /aria-pressed=\{view === "cards"\}/);
  assert.match(source, /aria-pressed=\{view === "table"\}/);
  assert.match(source, /question-table/);
});

test("Question Bank keeps server-backed search, supported filters, empty states, and actions", () => {
  assert.match(source, /questionsApi\s*\.\s*list\(page \* PAGE_SIZE/);
  assert.match(source, /matching question/);
  assert.match(source, /No questions match these filters/);
  assert.match(source, /questionsApi\.remove/);
  assert.match(source, /\/teacher\/questions\/\$\{question\.id\}\/edit/);
});

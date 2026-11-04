import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const client = source("../src/lib/learning.ts");
const practice = source("../src/components/practice-hub.tsx");
const dashboard = source("../src/components/student-dashboard.tsx");

test("practice client uses the authenticated same-origin API route", () => {
  assert.match(client, /apiFetch/);
  assert.match(client, /"\/student\/practice\/topics"/);
  assert.match(client, /"\/student\/practice\/sessions", "POST"/);
  assert.doesNotMatch(client, /user_id|Authorization/);
});

test("practice UI starts one selected topic session and keeps grading status visible", () => {
  assert.match(client, /topic_slug/);
  assert.match(practice, /learningApi\s*\.\s*start/);
  assert.match(practice, /Creating practice/);
  assert.match(practice, /awaiting grading/);
  assert.match(
    practice,
    /router\.push\(`\/student\/quizzes\/attempts\/\$\{attempt\.id\}`\)/,
  );
});

test("dashboard exposes server-calculated continue-learning data", () => {
  assert.match(dashboard, /learningApi\s*\.\s*summary/);
  assert.match(dashboard, /continue_learning/);
  assert.match(dashboard, /pending_grading_count/);
});

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const dashboard = source("../src/components/teacher-dashboard.tsx");

test("teacher dashboard derives operational counts from authorized existing APIs", () => {
  assert.match(dashboard, /gradingRequest<Queue>/);
  assert.match(dashboard, /quizRequest<StaffQuiz\[\]>/);
  assert.match(dashboard, /recruitmentApi\.staff/);
  assert.match(dashboard, /announcementsApi\.managed/);
  assert.match(dashboard, /status_counts\.SUBMITTED/);
  assert.match(dashboard, /status_counts\.UNDER_REVIEW/);
});

test("teacher dashboard provides loading, retry, empty, and operational actions", () => {
  assert.match(dashboard, /Loading your teaching workspace/);
  assert.match(dashboard, /Retry/);
  assert.match(
    dashboard,
    /No submitted grading or demonstrator applications need\s+attention/,
  );
  assert.match(dashboard, /\/teacher\/grading/);
  assert.match(dashboard, /\/teacher\/announcements/);
  assert.match(dashboard, /\/teacher\/recruitment/);
  assert.doesNotMatch(dashboard, /localStorage|mock|placeholder/i);
});

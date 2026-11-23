import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const auth = source("../src/components/auth-provider.tsx");
const form = source("../src/components/auth-form.tsx");
const fixtures = source("../src/lib/demo-fixtures.ts");
const provider = source("../src/components/demo-provider.tsx");
const guest = source("../src/components/guest-mode.tsx");

test("Guest Mode is public and skips authenticated session restoration", () => {
  assert.match(auth, /const demoPage = path === "\/demo"/);
  assert.match(auth, /if \(demoPage\)/);
  assert.match(auth, /demoPage \|\|/);
  assert.match(form, /href="\/demo"/);
});

test("Guest fixtures remain original, temporary, and start with exactly two ungraded submissions", () => {
  assert.match(fixtures, /Foundations of Discrete Mathematics/);
  assert.equal((fixtures.match(/id: "submission-/g) ?? []).length, 2);
  assert.match(fixtures, /freshDemoState/);
  assert.match(fixtures, /JSON\.parse\(JSON\.stringify/);
  assert.match(provider, /setState\(freshDemoState\(\)\)/);
  assert.match(
    provider,
    /Guest Mode does not save grades, contact students, or send notifications/,
  );
});

test("Guest quiz, student interactions, and lecturer controls remain local", () => {
  assert.ok((fixtures.match(/id: "q[1-8]"/g) ?? []).length >= 8);
  for (const method of [
    "chooseQuizAnswer",
    "submitQuiz",
    "retakeQuiz",
    "saveTask",
    "deleteTask",
    "markAllNotificationsRead",
    "completeLesson",
    "saveQuestion",
    "deleteQuestion",
    "saveAssessment",
    "toggleAssessmentPublication",
    "saveLesson",
    "toggleLessonPublication",
    "gradeSubmission",
    "sendDemoMessage",
  ])
    assert.match(provider, new RegExp(method));
  assert.match(guest, /Retake quiz/);
  assert.match(guest, /Mark all read/);
  assert.match(guest, /Mark lesson complete/);
  assert.match(guest, /View sample/);
  assert.match(guest, /Question Bank/);
  assert.match(guest, /Preview as student/);
  assert.match(guest, /Complete demo review/);
  assert.match(guest, /Sample conversation/);
  assert.match(guest, /state\.lessons\.filter\(/);
  assert.match(guest, /state\.assessments\.filter\(/);
});

test("Guest workspace has role switching, safe document previews, and no production side effects", () => {
  assert.match(guest, /Student Demo/);
  assert.match(guest, /Lecturer Demo/);
  assert.match(guest, /Reset Demo/);
  assert.match(guest, /Exit Demo/);
  assert.match(guest, /University Content — Restricted Access/);
  assert.match(guest, /SAMPLE DOCUMENT PREVIEW/);
  assert.match(guest, /No PDF has been[\s\S]{0,80}requested/);
  assert.match(auth, /if \(demoPage\) return;/);
  assert.match(auth, /if \(!user && !publicPage\)/);
  assert.doesNotMatch(
    guest,
    /@\/lib\/(auth|quizzes|course|learning|study-partner)/,
  );
  assert.doesNotMatch(
    `${guest}\n${provider}\n${fixtures}`,
    /apiFetch|authRequest|fetch\(|googleapis|drive\.files/,
  );
});

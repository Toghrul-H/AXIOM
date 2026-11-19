import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const shell = source("../src/components/app-shell.tsx");
const quizzes = source("../src/components/quiz-list.tsx");
const page = source("../src/app/student/page.tsx");
const preview = source("../src/components/student-preview-dashboard.tsx");
const auth = source("../src/components/auth-provider.tsx");

test("Student Preview hides private student destinations and uses a neutral dashboard", () => {
  assert.match(shell, /!studentView && user\?\.is_active/);
  assert.match(shell, /if \(teacher && user && \["LECTURER", "ADMIN"\]/);
  assert.match(auth, /path\.startsWith\("\/student\/course"\)/);
  assert.match(auth, /path\.startsWith\("\/student\/quizzes"\)/);
  assert.match(page, /studentView \? <StudentPreviewDashboard/);
  assert.match(
    preview,
    /Only resources that are published and accessible to students/,
  );
  assert.doesNotMatch(preview, /tasksApi|learningApi|useProgress|markRead/);
});

test("Student Preview loads active quizzes but never starts attempts or loads history", () => {
  assert.match(
    quizzes,
    /historyOnly \? Promise\.resolve\(\[\]\) : quizzesApi\.list/,
  );
  assert.match(
    quizzes,
    /studentView \? Promise\.resolve\(\[\]\) : quizzesApi\.history/,
  );
  assert.match(quizzes, /disabled=\{busy \|\| studentView\}/);
  assert.match(quizzes, /Preview only/);
  assert.match(quizzes, /!quizzes && !error/);
  assert.match(quizzes, />\s*Retry\s*</);
});

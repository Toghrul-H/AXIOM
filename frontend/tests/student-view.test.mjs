import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const auth = source("../src/components/auth-provider.tsx");
const shell = source("../src/components/app-shell.tsx");
const dashboard = source("../src/components/teacher-dashboard.tsx");

test("only lecturers and admins can enable the local Student View flag", () => {
  assert.match(auth, /\["LECTURER", "ADMIN"\]\.includes\(user\.role\)/);
  assert.match(auth, /axiom-student-view/);
  assert.match(auth, /router\.push\("\/student"\)/);
  assert.match(auth, /!previewingAsStudent/);
});

test("Student View preserves the real session and provides both entry and return controls", () => {
  assert.match(auth, /setAuth\(state\)/);
  assert.match(shell, /You are viewing AXIOM as a student/);
  assert.match(shell, /Return to Lecturer View/);
  assert.match(
    shell,
    /Student-specific data and\s+write actions are unavailable/,
  );
  assert.match(shell, /Student View/);
  assert.match(dashboard, /enterStudentView/);
});

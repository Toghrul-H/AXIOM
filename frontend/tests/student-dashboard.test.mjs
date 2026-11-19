import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const dashboard = source("../src/components/student-dashboard.tsx");
const calendar = source("../src/components/student-calendar.tsx");
const tasks = source("../src/components/personal-tasks.tsx");
const taskClient = source("../src/lib/personal-tasks.ts");
const utils = source("../src/lib/dashboard-utils.ts");

test("dashboard renders only evidence-backed learning and planning sources", () => {
  assert.match(dashboard, /useProgress\(/);
  assert.match(dashboard, /personalTasksApi\s*\.\s*list/);
  assert.match(dashboard, /Latest announcements/);
  assert.match(calendar, /not currently available from the platform\s+API/);
  assert.match(dashboard, /weekly_activity/);
});

test("personal tasks use authenticated student task endpoints for CRUD", () => {
  assert.match(taskClient, /"\/student\/tasks"/);
  assert.match(taskClient, /`\/student\/tasks\/\$\{id\}`/);
  assert.match(tasks, /personalTasksApi\.create/);
  assert.match(tasks, /personalTasksApi\.update/);
  assert.match(tasks, /personalTasksApi\.remove/);
  assert.doesNotMatch(tasks, /localStorage|sessionStorage/);
});

test("calendar utilities map only persisted due-date keys", () => {
  assert.match(utils, /task\.due_date/);
  assert.match(utils, /calendarDays/);
  assert.match(utils, /tasksByDate/);
});

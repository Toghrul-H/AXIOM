import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const workspace = readFileSync(
  new URL("../src/components/course-workspace.tsx", import.meta.url),
  "utf8",
);
const styles = readFileSync(
  new URL("../src/app/axiom.css", import.meta.url),
  "utf8",
);

test("student Course Workspace exposes only supported learning sections", () => {
  assert.match(
    workspace,
    /type StudentCourseTab = "overview" \| "materials" \| "practice" \| "interactive"/,
  );
  for (const label of [
    "Overview",
    "Materials",
    "Practice",
    "Interactive tools",
  ])
    assert.match(workspace, new RegExp(`label: "${label}"`));
  assert.match(workspace, /href="\/student\/practice"/);
  assert.match(workspace, /href="\/student\/course\/visualizations"/);
  assert.match(workspace, /<PublicMaterials\s+materials=\{group\.materials\}/);
  assert.match(workspace, /No published materials yet/);
  assert.doesNotMatch(workspace, /completion percentage|academic date/i);
});

test("Course Workspace tabs are native keyboard-accessible controls with responsive overflow", () => {
  assert.match(
    workspace,
    /<nav\s+className="course-workspace-tabs"\s+aria-label="Course learning sections"\s*>/,
  );
  assert.match(
    workspace,
    /aria-current=\{active === tab\.id \? "page" : undefined\}/,
  );
  assert.match(styles, /\.course-workspace-tabs \{/);
  assert.match(styles, /overflow-x: auto/);
  assert.match(styles, /\.course-workspace-tabs button\.is-active \{/);
});

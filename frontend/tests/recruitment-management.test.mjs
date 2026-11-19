import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(
  new URL(
    "../src/components/demonstrator-recruitment-management.tsx",
    import.meta.url,
  ),
  "utf8",
);
const proxy = readFileSync(
  new URL("../src/app/api/recruitment/[[...parts]]/route.ts", import.meta.url),
  "utf8",
);

test("Accept and Reject open a native focused confirmation dialog without a PATCH", () => {
  const open = source.slice(
    source.indexOf("function openDecision"),
    source.indexOf("async function confirmDecision"),
  );
  assert.match(open, /decisionTrigger\.current = trigger/);
  assert.match(open, /setDecision\(\{ application, status \}\)/);
  assert.doesNotMatch(open, /recruitmentApi\.setStatus/);
  assert.match(source, /dialog\.showModal\(\)/);
  assert.match(source, /confirmDecisionButton\.current\?\.focus/);
  assert.match(source, /onCancel=\{\(event\) =>/);
  assert.match(
    source,
    /openDecision\(\s*application,\s*"ACCEPTED",\s*event\.currentTarget,?\s*\)/,
  );
  assert.match(
    source,
    /openDecision\(\s*application,\s*"REJECTED",\s*event\.currentTarget,?\s*\)/,
  );
});

test("confirmation PATCHes only once, preserves the selection after an error, and supports cancellation", () => {
  const confirm = source.slice(
    source.indexOf("async function confirmDecision"),
    source.indexOf("async function exportFile"),
  );
  assert.match(
    confirm,
    /if \(!decision \|\| !vacancyId \|\| decisionPending\) return/,
  );
  assert.match(confirm, /setDecisionPending\(true\)/);
  assert.match(
    confirm,
    /recruitmentApi\.setStatus\(\s*vacancyId,\s*decision\.application\.id,\s*decision\.status,?\s*\)/,
  );
  assert.match(confirm, /setDecision\(null\)/);
  assert.match(confirm, /await review\(vacancyId\);\s*await load\(\);/);
  const catchBody = confirm.slice(
    confirm.indexOf("catch"),
    confirm.indexOf("finally"),
  );
  assert.doesNotMatch(catchBody, /setDecision\(null\)/);
  assert.match(source, /disabled=\{decisionPending \|\| !decision\}/);
  assert.match(source, /onClick=\{closeDecision\}/);
  assert.match(proxy, /PATCH: .*applications/);
});

test("staff capacity uses accepted positions, while student cards avoid inferring filled capacity from applications", () => {
  const staff = readFileSync(
    new URL(
      "../src/components/demonstrator-recruitment-management.tsx",
      import.meta.url,
    ),
    "utf8",
  );
  const student = readFileSync(
    new URL(
      "../src/components/demonstrator-opportunities.tsx",
      import.meta.url,
    ),
    "utf8",
  );

  assert.match(
    staff,
    /vacancy\.accepted_count \/ vacancy\.available_positions/,
  );
  assert.match(
    staff,
    /aria-label=\{`\$\{vacancy\.accepted_count\} of \$\{vacancy\.available_positions\} positions filled`\}/,
  );
  assert.match(
    student,
    /Filled-position capacity is not published to applicants\./,
  );
  assert.doesNotMatch(student, /applicant_count[^\n]*filled/);
});

test("application management retains native confirmation and explicit Accept/Reject actions", () => {
  assert.match(source, /className="button recruitment-accept"/);
  assert.match(source, /className="button recruitment-reject"/);
  assert.match(source, /data-label="Actions"/);
  assert.match(source, /onClose=\{\(\) =>\s*window\.setTimeout/);
});

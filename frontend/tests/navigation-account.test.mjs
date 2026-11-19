import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const shell = source("../src/components/app-shell.tsx");
const profile = source("../src/components/account-pages.tsx");
const partner = source("../src/components/study-partner-profile-editor.tsx");
const messages = source("../src/app/student/messages/page.tsx");

test("navigation keeps authorized Messages separate from Study Partner", () => {
  assert.match(shell, /href: "\/student\/study-partner"/);
  assert.match(shell, /href: "\/student\/messages"/);
  assert.match(messages, /StudyPartnerChat/);
  assert.doesNotMatch(partner, /StudyPartnerChat/);
  assert.doesNotMatch(shell, /futureTools|Coming soon/);
});

test("shell persists collapsed navigation and exposes account destinations", () => {
  assert.match(shell, /axiom-sidebar-collapsed/);
  assert.match(shell, /\/account\/profile/);
  assert.match(shell, /\/account\/settings/);
  assert.match(shell, /mobile-bottom-nav/);
});

test("account pages do not pretend unsupported profile mutations exist", () => {
  assert.match(profile, /currently\s+support avatar upload/i);
  assert.match(profile, /not self-service/i);
  assert.doesNotMatch(profile, /type="file"|fetch\(|authRequest\(/);
});

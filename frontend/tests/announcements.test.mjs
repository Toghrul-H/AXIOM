import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
const source = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const manager = source("../src/components/announcement-manager.tsx");
const proxy = source("../src/app/api/announcements/[[...parts]]/route.ts");
const shell = source("../src/components/app-shell.tsx");
test("staff announcements use the authenticated allowlisted proxy", () => {
  assert.match(proxy, /GET: \^\$|GET: \/\^\$\//);
  assert.match(proxy, /publish|unpublish/);
  assert.match(proxy, /x-csrf-token/);
  assert.match(proxy, /Cache-Control/);
});
test("manager exposes only supported draft and publication actions", () => {
  assert.match(manager, /Save draft/);
  assert.match(manager, /Publish/);
  assert.match(manager, /Unpublish/);
  assert.match(manager, /window\.confirm/);
  assert.doesNotMatch(manager, /attachment|upload/i);
  assert.match(shell, /\/teacher\/announcements/);
});

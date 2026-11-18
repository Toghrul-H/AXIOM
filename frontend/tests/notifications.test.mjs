import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

const source = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const proxySource = source(
  "../src/app/api/notifications/[[...parts]]/route.ts",
);
const client = source("../src/lib/notifications.ts");
const center = source("../src/components/notification-center.tsx");
const shell = source("../src/components/app-shell.tsx");

function route(fetch, base = "https://api.example.test") {
  const compiled = ts.transpileModule(proxySource, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText;
  const exports = {};
  vm.runInNewContext(compiled, {
    exports,
    fetch,
    Response,
    Headers,
    process: { env: base ? { API_BASE_URL: base } : {} },
  });
  return exports;
}

function request(path = "", method = "GET") {
  const request = new Request(
    `https://web.example.test/api/notifications${path}`,
    {
      method,
      headers: {
        cookie: "dmi_session=test-session",
        "x-csrf-token": "test-csrf",
        origin: "https://web.example.test",
        "sec-fetch-site": "same-origin",
      },
    },
  );
  request.nextUrl = new URL(request.url);
  return request;
}

const context = (parts = []) => ({ params: Promise.resolve({ parts }) });

test("notification proxy forwards only the authenticated notification API", async () => {
  const calls = [];
  const handler = route(async (url, init) => {
    calls.push([String(url), init.method, init.headers.get("cookie")]);
    return Response.json({ items: [], next_cursor: null });
  });
  const listed = await handler.GET(request("?limit=20"), context());
  const unread = await handler.GET(
    request("/unread-count"),
    context(["unread-count"]),
  );
  const read = await handler.POST(
    request("/17/read", "POST"),
    context(["17", "read"]),
  );
  const readAll = await handler.POST(
    request("/read-all", "POST"),
    context(["read-all"]),
  );
  assert.equal(listed.status, 200);
  assert.equal(unread.status, 200);
  assert.equal(read.status, 200);
  assert.equal(readAll.status, 200);
  assert.deepEqual(calls, [
    [
      "https://api.example.test/notifications?limit=20",
      "GET",
      "dmi_session=test-session",
    ],
    [
      "https://api.example.test/notifications/unread-count",
      "GET",
      "dmi_session=test-session",
    ],
    [
      "https://api.example.test/notifications/17/read",
      "POST",
      "dmi_session=test-session",
    ],
    [
      "https://api.example.test/notifications/read-all",
      "POST",
      "dmi_session=test-session",
    ],
  ]);
  assert.equal(listed.headers.get("cache-control"), "no-store");
  assert.equal(
    (await handler.GET(request("/17/delete"), context(["17", "delete"])))
      .status,
    404,
  );
});

test("notification proxy fails closed when its backend is unavailable", async () => {
  const handler = route(() => assert.fail("fetch must not run"), "");
  const response = await handler.GET(request(), context());
  assert.equal(response.status, 503);
  assert.equal(response.headers.get("cache-control"), "no-store");
});

test("notification client and center support safe links, pagination, read actions, and polling", () => {
  assert.match(client, /unreadCount/);
  assert.match(client, /markRead/);
  assert.match(client, /markAllRead/);
  assert.match(client, /legacyRecruitment/);
  assert.match(client, /!link\.startsWith\("\/\/"\)/);
  assert.match(center, /30_000/);
  assert.match(center, /visibilitychange/);
  assert.match(center, /controller\.current\?\.abort/);
  assert.match(center, /notificationApi\.markRead/);
  assert.match(center, /notificationApi\.markAllRead/);
  assert.match(center, /Load more/);
  assert.match(center, /isDuplicatedLegacy/);
  assert.match(center, /notificationApi\.legacyRecruitment/);
  assert.match(shell, /NotificationCenter key=\{user\.id\}/);
  assert.match(shell, /NotificationCenter/);
  assert.doesNotMatch(center, /dangerouslySetInnerHTML/);
});

test("notification center retains historical recruitment fallback without duplicate unified entries", () => {
  assert.match(center, /source: "legacy"/);
  assert.match(center, /source: "unified"/);
  assert.match(center, /!isDuplicatedLegacy\(item, items\)/);
  assert.match(
    center,
    /document\.addEventListener\("visibilitychange", refresh\)/,
  );
  assert.match(center, /clearInterval\(timer\)/);
  assert.match(center, /controller\.current\?\.abort\(\)/);
});

test("notification presentation includes all supported event families", () => {
  for (const kind of [
    "STUDY_PARTNER_REQUEST_RECEIVED",
    "STUDY_PARTNER_CHAT_MESSAGE",
    "RECRUITMENT_VACANCY_OPEN",
    "RECRUITMENT_APPLICATION_",
    "COURSE_CHAPTER_PUBLISHED",
    "COURSE_LESSON_PUBLISHED",
    "QUIZ_AVAILABLE",
    "MANUAL_GRADING_COMPLETED",
  ]) {
    assert.match(client, new RegExp(kind));
  }
});

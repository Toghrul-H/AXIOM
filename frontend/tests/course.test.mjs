import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

const source = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const proxySource = source("../src/app/api/course/[[...parts]]/route.ts");
const client = source("../src/lib/course.ts");
const workspace = source("../src/components/course-workspace.tsx");
const shell = source("../src/components/app-shell.tsx");
const auth = source("../src/components/auth-provider.tsx");

function route(fetch) {
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
    process: { env: { API_BASE_URL: "https://api.example.test" } },
  });
  return exports;
}
function request(path, method = "GET", body) {
  const value = new Request(`https://web.example.test/api/course${path}`, {
    method,
    headers: {
      cookie: "dmi_session=session",
      "x-csrf-token": "csrf",
      origin: "https://web.example.test",
      "sec-fetch-site": "same-origin",
      "content-type": "application/json",
    },
    body,
  });
  value.nextUrl = new URL(value.url);
  return value;
}
const context = (parts) => ({ params: Promise.resolve({ parts }) });

test("course client uses only same-origin authenticated course routes", () => {
  for (const routeName of [
    "/course/chapters",
    "/course/manage/chapters",
    "/course/lessons",
    "publish",
    "unpublish",
    "reorder",
  ])
    assert.ok(client.includes(routeName));
  assert.doesNotMatch(
    client,
    /expected_answer|explanation|email|neptun|Authorization/iu,
  );
});

test("course proxy forwards authentication and only allowlisted paths", async () => {
  const calls = [];
  const handler = route(async (url, init) => {
    calls.push([
      String(url),
      init.method,
      init.headers.get("cookie"),
      init.headers.get("x-csrf-token"),
    ]);
    return Response.json({ ok: true });
  });
  assert.equal(
    (await handler.GET(request("/chapters"), context(["chapters"]))).status,
    200,
  );
  assert.equal(
    (
      await handler.GET(
        request("/manage/chapters"),
        context(["manage", "chapters"]),
      )
    ).status,
    200,
  );
  assert.equal(
    (
      await handler.POST(
        request("/lessons/9/unpublish", "POST", ""),
        context(["lessons", "9", "unpublish"]),
      )
    ).status,
    200,
  );
  assert.equal(
    (
      await handler.PUT(
        request("/chapters/3/lessons/reorder", "PUT", '{"ids":[2,1]}'),
        context(["chapters", "3", "lessons", "reorder"]),
      )
    ).status,
    200,
  );
  assert.equal(
    (
      await handler.GET(
        request("/manage/secrets"),
        context(["manage", "secrets"]),
      )
    ).status,
    404,
  );
  assert.deepEqual(calls, [
    [
      "https://api.example.test/course/chapters",
      "GET",
      "dmi_session=session",
      "csrf",
    ],
    [
      "https://api.example.test/course/manage/chapters",
      "GET",
      "dmi_session=session",
      "csrf",
    ],
    [
      "https://api.example.test/course/lessons/9/unpublish",
      "POST",
      "dmi_session=session",
      "csrf",
    ],
    [
      "https://api.example.test/course/chapters/3/lessons/reorder",
      "PUT",
      "dmi_session=session",
      "csrf",
    ],
  ]);
});

test("course UI separates student reading from staff management", () => {
  for (const expected of [
    "No published lessons yet",
    "Practice questions",
    "Course management",
    "Add chapter",
    "Add lesson",
    "Linked active practice questions",
    "Unpublish",
  ])
    assert.match(workspace, new RegExp(expected));
  assert.match(workspace, /MathText/);
  assert.match(shell, /href: "\/student\/course"/);
  assert.match(shell, /href: "\/teacher\/course"/);
  assert.match(auth, /path\.startsWith\("\/teacher\/course"\)/);
  assert.doesNotMatch(
    workspace,
    /expected_answer|correct_boolean|explanation.*question/iu,
  );
});

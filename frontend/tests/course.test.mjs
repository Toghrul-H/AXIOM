import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

const source = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const proxySource = source("../src/app/api/course/[[...parts]]/route.ts");
const client = source("../src/lib/course.ts");
const workspace = source("../src/components/course-workspace.tsx");
const materialUi = source("../src/components/course-materials.tsx");
const shell = source("../src/components/app-shell.tsx");
const auth = source("../src/components/auth-provider.tsx");
const previewDashboard = source(
  "../src/components/student-preview-dashboard.tsx",
);

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

test("course proxy does not forward stale JSON content lengths", async () => {
  const handler = route(
    async () =>
      new Response(JSON.stringify([{ id: 1, title: "Slides" }]), {
        headers: { "content-type": "application/json", "content-length": "6" },
      }),
  );
  const response = await handler.GET(
    request("/manage/materials"),
    context(["manage", "materials"]),
  );
  assert.equal(response.headers.get("content-length"), null);
  assert.deepEqual(await response.json(), [{ id: 1, title: "Slides" }]);
});

test("course proxy preserves raw upload bytes and private download headers", async () => {
  let uploadBody;
  const handler = route(async (_url, init) => {
    if (init.method === "PUT")
      uploadBody = new Uint8Array(await new Response(init.body).arrayBuffer());
    return new Response("pdf-bytes", {
      headers: {
        "content-type": "application/pdf",
        "content-disposition": 'attachment; filename="notes.pdf"',
        "content-length": "9",
      },
    });
  });
  const upload = request(
    "/materials/9/file",
    "PUT",
    new Uint8Array([0, 255, 1]),
  );
  upload.headers.set("content-type", "application/pdf");
  upload.headers.set("x-material-filename", "notes.pdf");
  assert.equal(
    (await handler.PUT(upload, context(["materials", "9", "file"]))).status,
    200,
  );
  assert.deepEqual([...uploadBody], [0, 255, 1]);
  const download = await handler.GET(
    request("/materials/9/download"),
    context(["materials", "9", "download"]),
  );
  assert.equal(
    download.headers.get("content-disposition"),
    'attachment; filename="notes.pdf"',
  );
  assert.equal(download.headers.get("cache-control"), "no-store");
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
  assert.match(materialUi, /Upload draft material/);
  assert.match(materialUi, /Preview/);
  assert.match(client, /X-Material-Filename/);
  assert.match(shell, /href: "\/student\/course"/);
  assert.match(shell, /href: "\/teacher\/course"/);
  assert.match(auth, /path\.startsWith\("\/teacher\/course"\)/);
  assert.doesNotMatch(
    workspace,
    /expected_answer|correct_boolean|explanation.*question/iu,
  );
});

test("Student Preview uses published-only endpoints and cannot start student work", () => {
  assert.ok(proxySource.includes("student-preview\\/materials\\/[1-9][0-9]*"));
  assert.match(client, /student-preview\/materials/);
  assert.match(workspace, /studentPreview=\{studentView\}/);
  assert.match(previewDashboard, /announcementsApi\s*\.list\(\)/);
  assert.match(
    previewDashboard,
    /never loads student progress, tasks, attempts, grades, messages, or Study Partner data/i,
  );
});

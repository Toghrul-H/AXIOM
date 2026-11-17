import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

const source = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const proxySource = source(
  "../src/app/api/study-partner/[[...parts]]/route.ts",
);
const profileClient = source("../src/lib/study-partner.ts");
const editor = source("../src/components/study-partner-profile-editor.tsx");
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
    process: { env: { API_BASE_URL: base } },
  });
  return exports;
}

function request(path = "", method = "GET", body) {
  const req = new Request(`https://web.example.test/api/study-partner${path}`, {
    method,
    headers: {
      cookie: "dmi_session=test-session",
      "x-csrf-token": "test-csrf",
      origin: "https://web.example.test",
      "sec-fetch-site": "same-origin",
      "content-type": "application/json",
    },
    body,
  });
  req.nextUrl = new URL(req.url);
  return req;
}

const context = (parts = []) => ({ params: Promise.resolve({ parts }) });

test("Study Partner profile client uses authenticated same-origin requests only", () => {
  assert.match(profileClient, /authRequest/);
  assert.match(profileClient, /"\/study-partner\/me"/);
  assert.doesNotMatch(profileClient, /email|neptun|Authorization/iu);
});

test("Study Partner proxy forwards cookies, CSRF, query and safe JSON response", async () => {
  const handler = route(async (url, init) => {
    assert.equal(
      String(url),
      "https://api.example.test/study-partner/me?view=profile",
    );
    assert.equal(init.method, "GET");
    assert.equal(init.headers.get("cookie"), "dmi_session=test-session");
    assert.equal(init.headers.get("x-csrf-token"), "test-csrf");
    assert.equal(init.cache, "no-store");
    return Response.json({ exists: false });
  });
  const response = await handler.GET(
    request("/me?view=profile"),
    context(["me"]),
  );
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.deepEqual(await response.json(), { exists: false });
});

test("Study Partner proxy forwards unchanged PUT profile payload and rejects other paths", async () => {
  const body = JSON.stringify({ display_name: "Ada", is_participating: true });
  const handler = route(async (url, init) => {
    assert.equal(String(url), "https://api.example.test/study-partner/me");
    assert.equal(init.method, "PUT");
    assert.equal(init.body, body);
    assert.equal(init.headers.get("x-csrf-token"), "test-csrf");
    return Response.json({ exists: true });
  });
  assert.equal(
    (await handler.PUT(request("/me", "PUT", body), context(["me"]))).status,
    200,
  );
  assert.equal(
    (await handler.GET(request("/partners"), context(["partners"]))).status,
    404,
  );
});

test("profile editor communicates visibility, privacy, availability and pause safeguards", () => {
  for (const expected of [
    "Your email, Neptun code, and exact availability are never shown",
    "Make my profile discoverable",
    "Pausing your profile will cancel any pending Study Partner requests",
    "Add availability",
    "WANT_TO_STUDY",
    "CAN_HELP",
  ])
    assert.match(editor, new RegExp(expected));
  assert.match(shell, /href: "\/student\/study-partner"/);
  assert.match(shell, /user\?\.is_active/);
});

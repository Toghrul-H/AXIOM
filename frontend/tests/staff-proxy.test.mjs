import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

// Exercise the actual route without adding a test framework or contacting production.
const source = readFileSync(
  new URL("../src/app/api/users/[[...parts]]/route.ts", import.meta.url),
  "utf8",
);
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
  },
}).outputText;
function route(fetch, base = "https://axiom-api-te6o.onrender.com") {
  const exports = {};
  vm.runInNewContext(compiled, {
    exports,
    fetch,
    Response,
    Headers,
    URL,
    process: { env: { API_BASE_URL: base } },
  });
  return exports;
}
function request(path, method = "GET", body) {
  const req = new Request(`https://example.vercel.app/api/users${path}`, {
    method,
    headers: {
      cookie: "dmi_session=test-session",
      "x-csrf-token": "test-csrf",
      origin: "https://example.vercel.app",
      "sec-fetch-site": "same-origin",
      "content-type": "application/json",
    },
    body,
  });
  req.nextUrl = new URL(req.url);
  return req;
}
const context = (parts = []) => ({ params: Promise.resolve({ parts }) });

test("list/search forwards session and query to canonical users URL, without caching", async () => {
  const users = [{ id: 7, email: "new-student@example.test", role: "STUDENT" }];
  const handler = route(async (url, init) => {
    assert.equal(
      String(url),
      "https://axiom-api-te6o.onrender.com/users?q=new%40example.test&offset=0&limit=20",
    );
    assert.equal(init.headers.get("cookie"), "dmi_session=test-session");
    assert.equal(init.method, "GET");
    assert.equal(init.cache, "no-store");
    assert.equal(init.redirect, "manual");
    return Response.json(users);
  });
  const response = await handler.GET(
    request("?q=new%40example.test&offset=0&limit=20"),
    context(),
  );
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(response.headers.get("vary"), "Cookie");
  assert.deepEqual(await response.json(), users);
});

for (const [action, payload] of [
  ["role", { role: "LECTURER" }],
  ["status", { is_active: false }],
]) {
  test(`${action} update forwards session, CSRF and unchanged JSON`, async () => {
    const body = JSON.stringify(payload);
    const handler = route(async (url, init) => {
      assert.equal(
        String(url),
        `https://axiom-api-te6o.onrender.com/users/7/${action}`,
      );
      assert.equal(init.method, "POST");
      for (const key of [
        "cookie",
        "x-csrf-token",
        "origin",
        "sec-fetch-site",
        "content-type",
      ])
        assert.equal(init.headers.get(key), request("").headers.get(key));
      assert.equal(init.body, body);
      return Response.json({ id: 7, ...payload });
    });
    const response = await handler.POST(
      request(`/7/${action}`, "POST", body),
      context(["7", action]),
    );
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { id: 7, ...payload });
  });
}

for (const status of [401, 403]) {
  test(`preserves upstream ${status}; never bypasses authentication or RBAC`, async () => {
    const handler = route(async () =>
      Response.json({ detail: "Denied" }, { status }),
    );
    const response = await handler.GET(request(""), context());
    assert.equal(response.status, status);
    assert.deepEqual(await response.json(), { detail: "Denied" });
  });
}

test("does not expose upstream redirects to the browser", async () => {
  const handler = route(async () =>
    Response.redirect("https://axiom-api-te6o.onrender.com/users", 307),
  );
  const response = await handler.GET(request(""), context());
  assert.equal(response.status, 502);
  assert.equal(response.headers.get("location"), null);
});

test("rejects unsupported paths before forwarding", async () => {
  const handler = route(() => assert.fail("must not fetch"));
  assert.equal(
    (
      await handler.POST(
        request("/7/other", "POST", "{}"),
        context(["7", "other"]),
      )
    ).status,
    404,
  );
  assert.equal((await handler.GET(request("/7"), context(["7"]))).status, 404);
});

test("handles unavailable upstream", async () => {
  const handler = route(async () => {
    throw new Error("offline");
  });
  assert.equal((await handler.GET(request(""), context())).status, 503);
});

test("users requests cannot be intercepted by the old external rewrite", () => {
  const config = readFileSync(
    new URL("../next.config.ts", import.meta.url),
    "utf8",
  );
  assert.equal(config.includes('source: "/api/users/'), false);
});

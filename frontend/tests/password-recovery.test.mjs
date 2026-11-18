import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";
import * as jsx from "react/jsx-runtime";

const source = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

function load(path, imports = {}, globals = {}) {
  const exports = {};
  const code = ts.transpileModule(source(`../${path}`), {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      jsx: ts.JsxEmit.ReactJSX,
    },
  }).outputText;
  vm.runInNewContext(code, {
    exports,
    require: (id) => {
      if (id in imports) return imports[id];
      throw Error(id);
    },
    Headers,
    Response,
    URL,
    Error,
    ...globals,
  });
  return exports;
}

function auth(fetch) {
  return load("src/lib/auth.ts", {}, { fetch });
}

function recovery(fetch) {
  const authApi = auth(fetch);
  return load("src/lib/password-recovery.ts", { "./auth": authApi });
}

test("forgot-password always exposes the same generic confirmation", async () => {
  for (const email of ["student@inf.elte.hu", "unknown@inf.elte.hu"]) {
    const client = recovery(async (url, init) => {
      assert.equal(url, "/api/auth/forgot-password");
      assert.equal(init.method, "POST");
      assert.equal(init.credentials, "same-origin");
      assert.deepEqual(JSON.parse(init.body), { email });
      return Response.json({}, { status: 202 });
    });
    assert.equal(
      await client.requestPasswordReset(email),
      client.PASSWORD_RESET_REQUEST_MESSAGE,
    );
  }
});

test("reset uses only the POST body and maps invalid links to a safe message", async () => {
  const token = "a".repeat(43);
  const client = recovery(async (url, init) => {
    assert.equal(url, "/api/auth/reset-password");
    assert.equal(init.method, "POST");
    assert.deepEqual(JSON.parse(init.body), {
      token,
      password: "new-password-42!",
    });
    return new Response(null, { status: 204 });
  });
  assert.equal(
    (await client.resetPassword(token, "new-password-42!")).kind,
    "success",
  );
  const invalid = recovery(() => assert.fail("unexpected request"));
  assert.equal(
    (await invalid.resetPassword("bad", "new-password-42!")).kind,
    "invalid",
  );
  const expired = recovery(async () =>
    Response.json({ detail: "raw backend detail" }, { status: 400 }),
  );
  const result = await expired.resetPassword(token, "new-password-42!");
  assert.equal(result.kind, "invalid");
  assert.doesNotMatch(result.message, /raw backend detail/);
});

test("auth proxy allowlists only password recovery actions and forwards origin safeguards", async () => {
  const calls = [];
  const handler = load(
    "src/app/api/auth/[action]/route.ts",
    {},
    {
      process: { env: { API_BASE_URL: "https://backend.example" } },
      fetch: async (url, init) => {
        calls.push(String(url));
        assert.equal(init.headers.get("origin"), "https://web.example");
        assert.equal(init.headers.get("x-csrf-token"), "csrf");
        assert.equal(init.headers.get("cookie"), "dmi_session=test");
        assert.equal(init.cache, "no-store");
        return new Response(null, {
          status: String(url).endsWith("forgot-password") ? 202 : 204,
        });
      },
    },
  );
  const request = (action, body) =>
    new Request(`https://web.example/api/auth/${action}`, {
      method: "POST",
      headers: {
        cookie: "dmi_session=test",
        origin: "https://web.example",
        "x-csrf-token": "csrf",
        "content-type": "application/json",
      },
      body,
    });
  assert.equal(
    (
      await handler.POST(
        request("forgot-password", '{"email":"student@inf.elte.hu"}'),
        {
          params: Promise.resolve({ action: "forgot-password" }),
        },
      )
    ).status,
    202,
  );
  assert.equal(
    (
      await handler.POST(
        request(
          "reset-password",
          '{"token":"redacted","password":"new-password-42!"}',
        ),
        {
          params: Promise.resolve({ action: "reset-password" }),
        },
      )
    ).status,
    204,
  );
  assert.equal(
    (
      await handler.POST(request("not-allowed", "{}"), {
        params: Promise.resolve({ action: "not-allowed" }),
      })
    ).status,
    404,
  );
  assert.deepEqual(calls, [
    "https://backend.example/auth/forgot-password",
    "https://backend.example/auth/reset-password",
  ]);
});

test("reset component clears the token from history and keeps it out of storage", async () => {
  const slots = [];
  let cursor = 0;
  let effect;
  let replaced;
  const component = load(
    "src/components/password-recovery.tsx",
    {
      "react/jsx-runtime": jsx,
      react: {
        useState: (initial) => {
          const index = cursor++;
          if (!(index in slots)) slots[index] = initial;
          return [slots[index], (value) => (slots[index] = value)];
        },
        useRef: (initial) => {
          const index = cursor++;
          return (slots[index] ??= { current: initial });
        },
        useEffect: (callback) => {
          effect = callback;
        },
      },
      "next/link": { default: "a" },
      "./wordmark": { Wordmark: "wordmark" },
      "@/lib/password-recovery": {
        requestPasswordReset: async () => "",
        resetPassword: async () => ({ kind: "success", message: "ok" }),
      },
    },
    {
      window: {
        location: {
          href: `https://example.test/reset-password?token=${"b".repeat(43)}`,
        },
        history: {
          state: {},
          replaceState: (_state, _title, url) => (replaced = url),
        },
      },
    },
  );
  component.ResetPassword();
  effect();
  await Promise.resolve();
  assert.equal(replaced, "/reset-password");
  const componentSource = source("../src/components/password-recovery.tsx");
  assert.doesNotMatch(
    componentSource,
    /localStorage|sessionStorage|dangerouslySetInnerHTML/,
  );
});

test("login and recovery UI provide safe password validation affordances", () => {
  const login = source("../src/components/auth-form.tsx");
  const recoveryUi = source("../src/components/password-recovery.tsx");
  assert.match(login, /href="\/forgot-password"/);
  assert.match(recoveryUi, /Passwords do not match/);
  assert.match(recoveryUi, /12–128 characters/);
  assert.match(recoveryUi, /autoComplete="new-password"/);
  assert.match(recoveryUi, /role="alert"/);
});

test("password-recovery routes remain public while protected routes remain guarded", () => {
  const provider = load("src/components/auth-provider.tsx", {
    react: {
      createContext: () => ({}),
      useContext: () => null,
      useEffect: () => {},
      useState: () => [null, () => {}],
    },
    "react/jsx-runtime": jsx,
    "next/link": { default: "a" },
    "next/navigation": { usePathname: () => "/", useRouter: () => ({}) },
    "@/lib/auth": {},
    "./app-shell": { AppShell: "app-shell" },
  });

  for (const path of ["/forgot-password", "/reset-password", "/privacy"]) {
    const access = provider.authRouteAccess(path);
    assert.equal(access.publicPage, true);
    assert.equal(access.redirectAuthenticated, false);
  }
  assert.equal(provider.authRouteAccess("/privacy").privacyPage, true);
  assert.equal(provider.authRouteAccess("/teacher").publicPage, false);
  assert.equal(provider.authRouteAccess("/login").redirectAuthenticated, true);
  assert.equal(provider.authRouteAccess("/verify-email").publicPage, true);
});

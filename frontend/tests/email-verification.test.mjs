import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";
import * as jsx from "react/jsx-runtime";

test("verification page reads URL, clears it and shares request across effect replay", async () => {
  const token = "b".repeat(43);
  const slots = [];
  let cursor = 0;
  let effect;
  let calls = 0;
  let replaced;
  const component = load(
    "src/components/email-verification.tsx",
    {
      "react/jsx-runtime": jsx,
      react: {
        useState: (initial) => {
          const i = cursor++;
          if (!(i in slots)) slots[i] = initial;
          return [
            slots[i],
            (value) => {
              slots[i] = value;
            },
          ];
        },
        useRef: (initial) => {
          const i = cursor++;
          return (slots[i] ??= { current: initial });
        },
        useEffect: (callback) => {
          effect = callback;
        },
      },
      "next/link": { default: "a" },
      "./wordmark": { Wordmark: "wordmark" },
      "@/lib/email-verification": {
        verifyEmail: async (value) => {
          assert.equal(value, token);
          calls++;
          return { kind: "success", message: "Email verified successfully." };
        },
      },
    },
    {
      window: {
        location: { href: `https://example.test/verify-email?token=${token}` },
        history: {
          state: {},
          replaceState: (_state, _title, url) => {
            replaced = url;
          },
        },
      },
    },
  );
  component.VerifyEmail();
  const cleanup = effect();
  cleanup();
  effect();
  await Promise.resolve();
  cursor = 0;
  const tree = component.VerifyEmail();
  assert.equal(calls, 1);
  assert.equal(replaced, "/verify-email");
  assert.ok(
    nodes(tree).some(
      (n) => n.props?.children === "Email verified successfully.",
    ),
  );
});

function load(path, imports = {}, globals = {}) {
  const exports = {};
  const source = readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
  const code = ts.transpileModule(source, {
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
function api(fetch) {
  return load("src/lib/auth.ts", {}, { fetch });
}
function verification(fetch) {
  return load("src/lib/email-verification.ts", { "./auth": api(fetch) });
}

test("verification sends token only in same-origin POST body and handles success", async () => {
  const token = "a".repeat(43);
  const lib = verification(async (url, init) => {
    assert.equal(url, "/api/auth/verify-email");
    assert.equal(init.credentials, "same-origin");
    assert.equal(init.method, "POST");
    assert.equal(JSON.parse(init.body).token, token);
    return new Response(null, { status: 204 });
  });
  assert.equal(
    (await lib.verifyEmail(token)).message,
    "Email verified successfully.",
  );
});
test("missing/malformed tokens never make requests", async () => {
  const lib = verification(() => assert.fail("unexpected request"));
  assert.match((await lib.verifyEmail(null)).message, /missing/);
  assert.equal((await lib.verifyEmail("bad")).kind, "invalid");
});
for (const status of [400, 422, 429, 503]) {
  test(`verification handles ${status}`, async () => {
    const lib = verification(async () =>
      Response.json({ detail: "Rejected" }, { status }),
    );
    const result = await lib.verifyEmail("a".repeat(43));
    assert.equal(
      result.kind,
      [400, 422].includes(status) ? "invalid" : "error",
    );
    if (status === 400) assert.match(result.message, /expired, already used/);
  });
}
test("network failures are recoverable", async () => {
  const lib = verification(async () => {
    throw Error("network");
  });
  assert.equal((await lib.verifyEmail("a".repeat(43))).kind, "error");
});
test("resend uses safe generic wording and correct endpoint", async () => {
  const lib = verification(async (url, init) => {
    assert.equal(url, "/api/auth/resend-verification");
    assert.equal(JSON.parse(init.body).email, "student@inf.elte.hu");
    return Response.json({}, { status: 202 });
  });
  assert.match(
    await lib.resendVerification("student@inf.elte.hu"),
    /^If an unverified AXIOM account exists/,
  );
});

function nodes(node) {
  if (!node || typeof node !== "object") return [];
  return [node, ...[node.props?.children].flat(Infinity).flatMap(nodes)];
}
function formHarness(register, request) {
  const state = [];
  let cursor = 0;
  const navigation = [];
  const signedIn = [];
  const auth = api(() => {});
  const loaded = load(
    "src/components/auth-form.tsx",
    {
      "react/jsx-runtime": jsx,
      react: {
        useState: (initial) => {
          const i = cursor++;
          if (!(i in state)) state[i] = initial;
          return [
            state[i],
            (value) => {
              state[i] = value;
            },
          ];
        },
      },
      "next/link": { default: "a" },
      "next/navigation": {
        useRouter: () => ({ replace: (path) => navigation.push(path) }),
      },
      "@/lib/auth": { ...auth, authRequest: request(auth) },
      "./auth-provider": {
        useAuth: () => ({ signIn: (value) => signedIn.push(value) }),
      },
      "./wordmark": { Wordmark: "wordmark" },
    },
    {
      FormData: class {
        get(key) {
          return key === "email" ? "student@inf.elte.hu" : "test-password-123";
        }
      },
    },
  );
  const render = () => {
    cursor = 0;
    return loaded.AuthForm({ register });
  };
  return {
    render,
    navigation,
    signedIn,
    submit: async () =>
      nodes(render())
        .find((n) => n.type === "form")
        .props.onSubmit({ preventDefault() {}, currentTarget: {} }),
  };
}
test("registration navigates to check-email without login or role selector", async () => {
  const h = formHarness(true, () => async (path, method, body) => {
    assert.equal(path, "/auth/register");
    assert.equal(method, "POST");
    assert.deepEqual(Object.keys(body).sort(), ["email", "password"]);
  });
  assert.equal(
    nodes(h.render()).some(
      (n) => n.type === "select" || n.props?.name === "role",
    ),
    false,
  );
  await h.submit();
  assert.deepEqual(h.navigation, ["/check-email?registered=1"]);
  assert.equal(h.signedIn.length, 0);
});
test("unverified login exposes resend action only on backend verification rejection", async () => {
  const h = formHarness(false, (auth) => async () => {
    throw new auth.AuthRequestError(403, "Verify your email before signing in");
  });
  await h.submit();
  assert.ok(nodes(h.render()).some((n) => n.props?.href === "/check-email"));
  assert.equal(h.signedIn.length, 0);
});
test("verified login retains signIn flow", async () => {
  const h = formHarness(false, () => async () => ({
    user: { role: "STUDENT" },
    csrf_token: "test",
  }));
  await h.submit();
  assert.equal(h.signedIn.length, 1);
});
test("backend domain validation is displayed", async () => {
  const auth = api(async () =>
    Response.json({ detail: [{ msg: "Use @inf.elte.hu" }] }, { status: 422 }),
  );
  const h = formHarness(true, () => auth.authRequest);
  await h.submit();
  assert.ok(
    nodes(h.render()).some(
      (n) =>
        n.props?.role === "alert" && n.props.children === "Use @inf.elte.hu",
    ),
  );
});

test("auth proxy forwards cookies/CSRF, preserves HttpOnly Set-Cookie and canonical verification path", async () => {
  const handler = load(
    "src/app/api/auth/[action]/route.ts",
    {},
    {
      process: { env: { API_BASE_URL: "https://backend.example" } },
      fetch: async (url, init) => {
        assert.equal(url, "https://backend.example/auth/verify-email");
        assert.equal(init.headers.get("cookie"), "dmi_session=test");
        assert.equal(init.headers.get("x-csrf-token"), "csrf");
        assert.equal(init.redirect, "manual");
        return new Response(null, {
          status: 204,
          headers: {
            "Set-Cookie": "dmi_session=test; HttpOnly; Secure; Path=/",
          },
        });
      },
    },
  );
  const response = await handler.POST(
    new Request("https://frontend.example/api/auth/verify-email", {
      method: "POST",
      headers: { cookie: "dmi_session=test", "x-csrf-token": "csrf" },
      body: "{}",
    }),
    { params: Promise.resolve({ action: "verify-email" }) },
  );
  assert.equal(response.status, 204);
  assert.match(response.headers.get("set-cookie"), /HttpOnly/);
  assert.equal(response.headers.get("cache-control"), "no-store");
});

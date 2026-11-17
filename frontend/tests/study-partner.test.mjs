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
const community = source("../src/components/study-partner-community.tsx");
const chat = source("../src/components/study-partner-chat.tsx");
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

test("Study Partner client uses authenticated same-origin requests only", () => {
  assert.match(profileClient, /authRequest/);
  assert.match(profileClient, /"\/study-partner\/me"/);
  assert.match(profileClient, /\/study-partner\/partners/);
  assert.match(profileClient, /"\/study-partner\/requests/);
  assert.match(profileClient, /"\/study-partner\/blocks/);
  assert.match(profileClient, /"\/study-partner\/chats"/);
  assert.match(profileClient, /\/messages/);
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

test("Study Partner proxy forwards unchanged PUT profile payload and rejects unsupported paths", async () => {
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
    (await handler.GET(request("/unknown"), context(["unknown"]))).status,
    404,
  );
});

test("Study Partner proxy forwards discovery, request actions, blocks, and chat routes", async () => {
  const calls = [];
  const handler = route(async (url, init) => {
    calls.push([String(url), init.method, init.body]);
    return Response.json({ ok: true });
  });
  await handler.GET(
    request("/partners?topic_id=4&study_format=ONLINE"),
    context(["partners"]),
  );
  await handler.POST(
    request("/requests", "POST", '{"recipient_profile_id":7}'),
    context(["requests"]),
  );
  await handler.POST(
    request("/requests/7/accept", "POST", ""),
    context(["requests", "7", "accept"]),
  );
  await handler.DELETE(
    request("/blocks/7", "DELETE"),
    context(["blocks", "7"]),
  );
  await handler.GET(
    request("/chats/7/messages?offset=0&limit=100"),
    context(["chats", "7", "messages"]),
  );
  await handler.POST(
    request("/chats/7/messages", "POST", '{"content":"Hello"}'),
    context(["chats", "7", "messages"]),
  );
  assert.deepEqual(calls, [
    [
      "https://api.example.test/study-partner/partners?topic_id=4&study_format=ONLINE",
      "GET",
      undefined,
    ],
    [
      "https://api.example.test/study-partner/requests",
      "POST",
      '{"recipient_profile_id":7}',
    ],
    ["https://api.example.test/study-partner/requests/7/accept", "POST", ""],
    ["https://api.example.test/study-partner/blocks/7", "DELETE", undefined],
    [
      "https://api.example.test/study-partner/chats/7/messages?offset=0&limit=100",
      "GET",
      undefined,
    ],
    [
      "https://api.example.test/study-partner/chats/7/messages",
      "POST",
      '{"content":"Hello"}',
    ],
  ]);
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

test("community UI only uses public partner fields and protects request actions", () => {
  for (const expected of [
    "Find study partners",
    "Shared study topics",
    "Exact schedules stay private",
    "Send request",
    "Incoming",
    "Outgoing",
    "Block",
  ])
    assert.match(community, new RegExp(expected));
  assert.doesNotMatch(community, /neptun|email|availability\.map/iu);
});

test("chat UI uses text-safe rendering, validation, polling, and retry states", () => {
  for (const expected of [
    "Accepted Study Partner connections appear here.",
    "POL L_INTERVAL_MS".replace(" ", ""),
    "Messages can contain at most",
    "noopener noreferrer",
    "This conversation is no longer available.",
  ])
    assert.match(chat, new RegExp(expected));
  assert.ok(chat.includes("Shift+Enter adds a line"));
  assert.ok(chat.includes("new URL(part)"));
  assert.doesNotMatch(chat, /dangerouslySetInnerHTML|innerHTML/);
});

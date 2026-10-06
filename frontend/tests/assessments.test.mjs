import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";
import * as jsx from "react/jsx-runtime";

function load(path, imports = {}, globals = {}, extra = "") {
  const exports = {};
  const source =
    readFileSync(new URL(`../${path}`, import.meta.url), "utf8") + extra;
  const code = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      jsx: ts.JsxEmit.ReactJSX,
    },
  }).outputText;
  vm.runInNewContext(code, {
    exports,
    require: (id) => imports[id],
    Error,
    Headers,
    Response,
    URL,
    FormData,
    AbortController,
    ...globals,
  });
  return exports;
}
function lib(fetch = async () => Response.json([])) {
  return load("src/lib/assessments.ts", { "./auth": { apiFetch: fetch } });
}
function nodes(node) {
  return !node || typeof node !== "object"
    ? []
    : [node, ...[node.props?.children].flat(Infinity).flatMap(nodes)];
}
function ui(api, role = "LECTURER", states = []) {
  let cursor = 0;
  const navigation = [];
  const loaded = load(
    "src/components/assessment-editor.tsx",
    {
      "react/jsx-runtime": jsx,
      react: {
        useEffect: () => {},
        useRef: (value) => ({ current: value }),
        useState: (initial) => [states[cursor++] ?? initial, () => {}],
      },
      "next/link": { default: "a" },
      "next/navigation": {
        useRouter: () => ({ push: (path) => navigation.push(path) }),
      },
      "./auth-provider": { useAuth: () => ({ user: { role } }) },
      "./page-heading": { PageHeading: "heading" },
      "@/lib/assessments": { ...lib(), assessmentRequest: api },
    },
    {},
    "\nexport { EventEditor, Rooms, EditForm }; ",
  );
  return { ...loaded, navigation };
}
function form(values) {
  const result = new FormData();
  for (const [k, v] of Object.entries(values)) result.set(k, v);
  return result;
}
for (const role of ["LECTURER", "ADMIN", "STUDENT", "DEMONSTRATOR"]) {
  test(`${role} assessment page access`, () => {
    const component = ui(() => {}, role);
    const result = component.AssessmentAccess({ children: "editor" });
    assert.equal(result === "editor", ["LECTURER", "ADMIN"].includes(role));
  });
}
test("list empty state and create navigation", async () => {
  const component = ui(
    async (path, method, payload) => {
      assert.equal(path, "");
      assert.equal(method, "POST");
      assert.equal(payload.academic_year_start, 2026);
      return { id: 12 };
    },
    "LECTURER",
    [[]],
  );
  const tree = component.AssessmentList();
  assert.ok(
    nodes(tree).some(
      (n) =>
        typeof n.props?.children === "string" &&
        n.props.children.startsWith("No semester configurations"),
    ),
  );
  await nodes(tree)
    .find((n) => n.type === component.EditForm)
    .props.save(
      form({
        academic_year_start: "2026",
        term: "FALL",
        display_label: "Fall",
      }),
    );
  assert.deepEqual(component.navigation, ["/teacher/assessments/12"]);
});
test("existing configuration can be opened", () => {
  const component = ui(() => {}, "ADMIN", [
    [
      {
        id: 7,
        display_label: "Semester",
        academic_year_start: 2026,
        term: "FALL",
        updated_at: "2026-01-01",
      },
    ],
  ]);
  assert.ok(
    nodes(component.AssessmentList()).some(
      (n) => n.props?.href === "/teacher/assessments/7",
    ),
  );
});
test("event create/update/delete use actual API and human labels", async () => {
  const calls = [];
  const component = ui(async (...args) => {
    calls.push(args);
    return { id: 9 };
  });
  for (const value of [
    undefined,
    { id: 9, event_type: "MIDTERM", rooms: [] },
  ]) {
    const tree = component.EventEditor({
      type: "MIDTERM",
      value,
      base: "/7",
      update: () => {},
    });
    assert.ok(
      nodes(tree).some(
        (n) => n.type === "h2" && n.props.children === "Midterm test",
      ),
    );
    const edit = nodes(tree).find((n) => n.type === component.EditForm);
    await edit.props.save(form({ date: "2027-05-19" }));
    if (value) await edit.props.remove();
  }
  assert.deepEqual(
    calls.map((c) => [c[0], c[1]]),
    [
      ["/7/events", "POST"],
      ["/7/events/9", "PUT"],
      ["/7/events/9", "DELETE"],
    ],
  );
  assert.equal(calls[0][2].start_time, null);
});
test("room create/update/delete and structured groups", async () => {
  const calls = [];
  const component = ui(async (...args) => {
    calls.push(args);
    return { id: 3 };
  });
  const tree = component.Rooms({
    event: { rooms: [{ id: 3, room: "A", groups: [{ identifier: "lab" }] }] },
    path: "/7/events/9/rooms",
    update: () => {},
  });
  const forms = nodes(tree).filter((n) => n.type === component.EditForm);
  await forms[0].props.save(form({ room: "B", groups: "1, lab-A\n42" }));
  await forms[0].props.remove();
  await forms[1].props.save(form({ room: "C", groups: "X" }));
  assert.deepEqual(
    calls.map((c) => c[1]),
    ["PUT", "DELETE", "POST"],
  );
  assert.equal(
    JSON.stringify(calls[0][2].groups),
    JSON.stringify(["1", "lab-A", "42"]),
  );
  assert.throws(
    () => lib().roomInput(form({ room: "R", groups: "1, 1" })),
    /only once/,
  );
  assert.throws(
    () => lib().roomInput(form({ room: "R", groups: "" })),
    /at least one/,
  );
});
test("semester and group conflicts plus validation remain useful", async () => {
  const api = lib(async () => Response.json({}, { status: 409 }));
  await assert.rejects(
    api.assessmentRequest("", "POST", {}),
    /academic year and term/,
  );
  await assert.rejects(
    api.assessmentRequest("/7/events/9/rooms", "POST", {}),
    /practice group is already assigned/,
  );
  const validation = lib(async () =>
    Response.json(
      { detail: [{ msg: "End time must be later" }] },
      { status: 422 },
    ),
  );
  await assert.rejects(
    validation.assessmentRequest("/7/events/9", "PUT", {}),
    /End time/,
  );
});
test("proxy forwards all CRUD methods with cookies, CSRF and no cache", async () => {
  let expected;
  const handler = load(
    "src/app/api/assessment-configurations/[[...parts]]/route.ts",
    {},
    {
      process: { env: { API_BASE_URL: "https://backend.example" } },
      fetch: async (url, init) => {
        assert.equal(
          String(url),
          `https://backend.example/assessment-configurations${expected}`,
        );
        assert.equal(init.headers.get("cookie"), "dmi_session=test");
        assert.equal(init.headers.get("x-csrf-token"), "csrf");
        assert.equal(init.cache, "no-store");
        assert.equal(init.redirect, "manual");
        return Response.json({});
      },
    },
  );
  for (const [method, path] of [
    ["GET", ""],
    ["POST", ""],
    ["PATCH", "/7"],
    ["POST", "/7/events"],
    ["PUT", "/7/events/9"],
    ["POST", "/7/events/9/rooms"],
    ["PUT", "/7/events/9/rooms/3"],
    ["DELETE", "/7/events/9/rooms/3"],
  ]) {
    expected = path;
    const request = new Request(
      "https://frontend.example/api/assessment-configurations" + path,
      {
        method,
        headers: { cookie: "dmi_session=test", "x-csrf-token": "csrf" },
        ...(["POST", "PATCH", "PUT"].includes(method) ? { body: "{}" } : {}),
      },
    );
    request.nextUrl = new URL(request.url);
    const result = await handler[method](request, {
      params: Promise.resolve({ parts: path.split("/").filter(Boolean) }),
    });
    assert.equal(result.status, 200);
    assert.equal(result.headers.get("cache-control"), "no-store");
  }
});

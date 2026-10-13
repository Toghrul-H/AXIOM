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
        useState: (initial) => [
          states[cursor++] ??
            (typeof initial === "function" ? initial() : initial),
          () => {},
        ],
      },
      "next/link": { default: "a" },
      "next/navigation": {
        useRouter: () => ({ push: (path) => navigation.push(path) }),
      },
      "./auth-provider": { useAuth: () => ({ user: { role } }) },
      "./page-heading": { PageHeading: "heading" },
      "./document-preview": { DocumentWorkspace: "workspace" },
      "@/lib/document-preview": load("src/lib/document-preview.ts", { "./assessments": lib() }),
      "@/lib/assessments": { ...lib(), assessmentRequest: api },
    },
    {},
    "\nexport { EventEditor, Rooms, EditForm, PolicyEditor, SemesterRules, SubmissionFields }; ",
  );
  return { ...loaded, navigation };
}
function form(values) {
  const result = new FormData();
  for (const [k, v] of Object.entries(values)) result.set(k, v);
  return result;
}
test("scheduled, writing and arrival times stay separate in editor payload", () => {
  const payload = lib().eventInput(
    form({
      start_time: "10:00",
      end_time: "12:00",
      writing_start_time: "10:15",
      writing_end_time: "11:45",
      latest_arrival_time: "10:05",
    }),
    "ENDTERM",
  );
  assert.equal(payload.start_time, "10:00");
  assert.equal(payload.writing_start_time, "10:15");
  assert.equal(payload.writing_end_time, "11:45");
  assert.equal(payload.latest_arrival_time, "10:05");
  assert.equal(lib().eventInput(form({}), "ENDTERM").writing_start_time, null);
  const component = ui(() => {});
  const tree = component.EventEditor({
    type: "ENDTERM",
    value: { id: 1, rooms: [] },
    base: "/1",
    update: () => {},
  });
  const labels = nodes(tree)
    .filter((n) => n.type === "label")
    .map((n) => n.props.children[0]);
  for (const text of [
    "Scheduled start time",
    "Scheduled end time",
    "Actual writing start time",
    "Actual writing end time",
    "Latest arrival time",
  ])
    assert.ok(labels.includes(text));
});
for (const type of Object.keys(lib().eventLabels)) {
  test(`room section applicability: ${type}`, () => {
    const component = ui(() => {});
    const tree = component.EventEditor({
      type,
      value: { id: 9, event_type: type, rooms: [] },
      base: "/7",
      update: () => {},
    });
    const expected = [
      "MIDTERM",
      "ENDTERM",
      "SHORT_QUIZ_RETAKE",
      "TEST_RETAKE",
    ].includes(type);
    assert.equal(
      nodes(tree).some((n) => n.type === component.Rooms),
      expected,
    );
    if (expected) {
      const roomTree = component.Rooms({
        event: { rooms: [] },
        path: "/7/events/9/rooms",
        update: () => {},
      });
      assert.ok(
        nodes(roomTree).some(
          (n) =>
            typeof n.props?.children === "string" &&
            n.props.children.startsWith("Optional. Leave empty"),
        ),
      );
    }
  });
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
    ...[
      "DATES_OF_ASSESSMENTS",
      "ENDTERM_TEST_INFORMATION",
      "RULES_OF_ASSESSMENT",
      "RULES_OF_EARNING_PLUS_POINTS",
      "MIDTERM_TEST_INFORMATION",
      "TEST_RETAKE_INFORMATION",
      "COURSEWORK_ASSIGNMENT_INFORMATION",
    ].map((kind) => ["POST", `/7/documents/${kind}/preview`]),
    ["GET", "/7/rules"],
    ["PUT", "/7/rules"],
    ...["MIDTERM", "ENDTERM", "COURSEWORK", "SHORT_QUIZZES"].map((code) => [
      "PUT",
      `/7/policies/${code}`,
    ]),
    ...[
      "DATES_OF_ASSESSMENTS",
      "ENDTERM_TEST_INFORMATION",
      "RULES_OF_ASSESSMENT",
      "RULES_OF_EARNING_PLUS_POINTS",
      "MIDTERM_TEST_INFORMATION",
      "TEST_RETAKE_INFORMATION",
      "COURSEWORK_ASSIGNMENT_INFORMATION",
    ].map((kind) => ["GET", `/7/documents/${kind}/latex`]),
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

test("preview proxy preserves LaTeX and rejects unknown paths and mutation methods", async () => {
  let calls = 0;
  const handler = load(
    "src/app/api/assessment-configurations/[[...parts]]/route.ts",
    {},
    {
      process: { env: { API_BASE_URL: "https://backend.example" } },
      fetch: async () => {
        calls++;
        return new Response("\\documentclass{article}", {
          headers: { "content-type": "text/plain; charset=utf-8" },
        });
      },
    },
  );
  async function request(method, path) {
    const req = new Request(
      `https://frontend.example/api/assessment-configurations/${path}`,
      { method },
    );
    req.nextUrl = new URL(req.url);
    return handler[method](req, {
      params: Promise.resolve({ parts: path.split("/") }),
    });
  }
  const result = await request(
    "GET",
    "7/documents/MIDTERM_TEST_INFORMATION/latex",
  );
  assert.equal(await result.text(), "\\documentclass{article}");
  assert.ok(result.headers.get("content-type").startsWith("text/plain"));
  assert.equal(result.headers.get("vary"), "Cookie");
  for (const [method, path] of [
    ["GET", "7/documents/UNKNOWN/latex"],
    ["GET", "7/documents/../../secrets"],
    ["PUT", "7/documents/MIDTERM_TEST_INFORMATION/latex"],
    ["PUT", "7/policies/UNKNOWN"],
    ["DELETE", "7/rules"],
  ]) {
    assert.equal((await request(method, path)).status, 404);
  }
  assert.equal(calls, 1);
});

test("policy payload preserves optional values and fractional scores", () => {
  const payload = lib().policyInput(
    form({
      topics: " Graphs & sets ",
      maximum_score: "20.5",
      passing_score: "8",
      duration_minutes: "90",
      assessment_count: "10",
    }),
  );
  assert.equal(payload.topics, "Graphs & sets");
  assert.equal(payload.maximum_score, "20.5");
  assert.equal(payload.duration_minutes, 90);
  assert.equal(payload.assessment_count, 10);
  assert.equal(payload.permitted_equipment, null);
});
test("grade thresholds are explicit, never inferred", () => {
  assert.throws(() => lib().rulesInput(form({ grade_1: "0" })), /five/);
  const data = lib().rulesInput(
    form({
      grade_1: "0",
      grade_2: "48",
      grade_3: "66",
      grade_4: "84",
      grade_5: "102",
      plus_points_maximum: "10.5",
    }),
  );
  assert.equal(data.grade_boundaries.length, 5);
  assert.equal(data.plus_points_maximum, "10.5");
  assert.equal(lib().rulesInput(form({})).grade_boundaries.length, 0);
});
test("group deadlines serialize independently from scheduled time", () => {
  const data = lib().eventInput(
    form({
      start_time: "10:00",
      submission_deadline_time: "09:30",
      deadline_group_4: " G1 ",
      deadline_date_4: "2027-05-02",
      deadline_venue_4: " R1 ",
      deadline_group_8: "G2",
    }),
    "COURSEWORK_HAND_IN",
  );
  assert.equal(data.start_time, "10:00");
  assert.equal(data.submission_deadline_time, "09:30");
  assert.equal(data.group_deadlines.length, 2);
  assert.equal(data.group_deadlines[0].group_identifier, "G1");
  assert.equal(data.group_deadlines[0].venue, "R1");
  assert.equal(data.group_deadlines[1].deadline_date, null);
});
test("policy editor saves through existing authenticated assessment client", async () => {
  const calls = [];
  const component = ui(async (...args) => {
    calls.push(args);
    return { code: "ENDTERM" };
  });
  let saved;
  const tree = component.PolicyEditor({
    code: "ENDTERM",
    base: "/7",
    update: (value) => {
      saved = value;
    },
  });
  await tree.props.save(form({ maximum_score: "40", topics: "Graphs" }));
  assert.equal(calls[0][0], "/7/policies/ENDTERM");
  assert.equal(calls[0][1], "PUT");
  assert.equal(saved.code, "ENDTERM");
  const fields = nodes(tree).filter(
    (n) => n.type === "input" || n.type === "textarea",
  );
  assert.ok(fields.some((n) => n.props.name === "permitted_equipment"));
});
test("submission editor shows saved group overrides and plain-text seating field", () => {
  const component = ui(async () => {});
  const tree = component.SubmissionFields({
    value: {
      group_deadlines: [
        {
          group_identifier: "Tuesday",
          deadline_date: "2027-05-01",
          venue: "Room",
        },
      ],
    },
  });
  const inputs = nodes(tree).filter((n) => n.type === "input");
  assert.ok(
    inputs.some(
      (n) =>
        n.props.name === "deadline_group_0" &&
        n.props.defaultValue === "Tuesday",
    ),
  );
  assert.ok(
    inputs.some(
      (n) =>
        n.props.name === "deadline_date_0" &&
        n.props.defaultValue === "2027-05-01",
    ),
  );
  assert.ok(
    nodes(tree).some(
      (n) => n.type === "button" && n.props["data-assessment-change"],
    ),
  );
});

test("document workspaces retain canonical editors and show only relevant sections", () => {
  const api = async () => { throw Error("no request during navigation"); };
  const view = ui(api, "LECTURER", [{ id: 1, academic_year_start: 2030, term: "SPRING", display_label: "Test", events: [], policies: [] }]);
  const workspace = nodes(view.AssessmentDetail({id: "1"})).find(n => n.type === "workspace");
  const visibleNodes = node => !node || typeof node !== "object" || node.props?.hidden ? [] : [node, ...[node.props?.children].flat(Infinity).flatMap(visibleNodes)];
  const cases = {
    DATES_OF_ASSESSMENTS: [8,4], ENDTERM_TEST_INFORMATION: [1,1], RULES_OF_ASSESSMENT: [8,4],
    RULES_OF_EARNING_PLUS_POINTS: [0,0], MIDTERM_TEST_INFORMATION: [1,1], TEST_RETAKE_INFORMATION: [1,2], COURSEWORK_ASSIGNMENT_INFORMATION: [4,1],
  };
  for (const [kind,[events,policies]] of Object.entries(cases)) {
    const tree=workspace.props.children(kind), all=nodes(tree), visible=visibleNodes(tree);
    assert.equal(all.filter(n=>n.type===view.EventEditor).length,8);
    assert.equal(all.filter(n=>n.type===view.PolicyEditor).length,4);
    assert.equal(visible.filter(n=>n.type===view.EventEditor).length,events,kind);
    assert.equal(visible.filter(n=>n.type===view.PolicyEditor).length,policies,kind);
    for (const policy of visible.filter(n=>n.type===view.PolicyEditor)) {
      const fields=nodes(view.PolicyEditor(policy.props));
      for (const name of ["maximum_score","passing_score"]) assert.ok(fields.some(n=>n.type==='input' && n.props.name===name));
    }
  }
});

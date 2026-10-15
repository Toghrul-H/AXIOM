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
  const stateChanges = [];
  const loaded = load(
    "src/components/assessment-editor.tsx",
    {
      "react/jsx-runtime": jsx,
      react: {
        useEffect: () => {},
        useRef: (value) => ({ current: value }),
        useState: (initial) => {
          let value = states[cursor++] ?? (typeof initial === "function" ? initial() : initial);
          return [value, change => {value = typeof change === "function" ? change(value) : change; stateChanges.push(value);}];
        },
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
  return { ...loaded, navigation, stateChanges };
}
function form(values) {
  const result = new FormData();
  for (const [k, v] of Object.entries(values)) result.set(k, v);
  return result;
}

test('save baseline advances only after success and failed saves preserve it', async () => {
  const preview = load('src/lib/document-preview.ts', {'./assessments': lib()});
  const values = form({venue:'New hall'});
  const element = {dataset:{savedValues:preview.formValues(form({venue:'Old hall'}))}, values};
  const module = load('src/components/assessment-editor.tsx', {
    'react/jsx-runtime':jsx,
    react:{useEffect:()=>{},useRef:initial=>({current:initial}),useState:initial=>[initial,()=>{}]},
    '@/lib/document-preview':preview,
  }, {FormData:class {constructor(form){const copy = new FormData(); for (const [key,value] of form.values) copy.append(key,value); return copy;}}}, '\nexport { EditForm };');
  // FormData is copied so the baseline represents the submitted request.
  // Node FormData cannot clone directly; provide the browser-form equivalent.
  let resolve, reject;
  const pendingSave = () => new Promise((ok, fail) => {resolve=ok;reject=fail;});
  const tree = module.EditForm({children:null,label:'event',save:pendingSave});
  const original = element.dataset.savedValues;
  const request = tree.props.onSubmit({preventDefault(){},currentTarget:element});
  reject(Error('Server rejected save'));
  await request;
  assert.equal(element.dataset.savedValues,original);
  const success = tree.props.onSubmit({preventDefault(){},currentTarget:element});
  assert.equal(element.dataset.savedValues,original);
  resolve(); await success;
  assert.equal(element.dataset.savedValues,preview.formValues(values));
});
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
            n.props.children === "+ Add room",
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
        (n) => n.type === "h2" && [n.props.children].flat().join("").includes("Midterm test — Schedule & Logistics"),
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
test("room rows validate, save, swap, remove and reload multiple assignments", async () => {
  let records=[{id:1,room:"A",groups:[{identifier:"1"}]},{id:2,room:"B",groups:[{identifier:"2"}]}], serial=2;
  const api=lib(async (url,options) => {
    if(options.method === "DELETE") { records=records.filter(r=>r.id!==Number(url.split("/").at(-1))); return new Response(null,{status:204}); }
    const payload=JSON.parse(options.body), room={id:++serial,room:payload.room,groups:payload.groups.map(identifier=>({identifier}))}; records.push(room);return Response.json(room);
  });
  const saved=new Map(records.map(r=>[String(r.id),r]));
  const data=form({room_1:"B",groups_1:"2",room_2:"A",groups_2:"1",room_new:"C",groups_new:"3,4"});
  ["1","2","new","empty"].forEach(key=>data.append("room_key",key));
  const rows=api.roomRowsInput(data);assert.equal(rows.length,3);
  await api.saveRoomRows("/1/events/2/rooms",rows,saved,()=>{});
  assert.equal(records.length,3);assert.equal(records[2].groups.length,2);
  await api.saveRoomRows("/1/events/2/rooms",rows.slice(0,2),saved,()=>{});assert.equal(records.length,2);
  const component=ui();const tree=component.Rooms({event:{rooms:records,event_type:"MIDTERM"},path:"/1/events/2/rooms",update:()=>{}});
  assert.equal(nodes(tree).filter(n=>n.type==='input' && n.props.name.startsWith('room_') && n.props.type!=='hidden').length,2);
  assert.equal(nodes(tree).filter(n=>n.type===component.EditForm).length,1);
  assert.ok(nodes(tree).some(n=>n.type==='button' && n.props.children==='+ Add room'));
  data.set('groups_new','1');assert.throws(()=>api.roomRowsInput(data),/Room row 3.*multiple rooms/);
  data.set('groups_new','');assert.throws(()=>api.roomRowsInput(data),/Room row 3.*at least one/);
  // Validation scope is one event, not a global practice-group registry.
  assert.equal(api.roomRowsInput(formWithRoom('A','1')).length,1);
});
function formWithRoom(room,groups) {const result=form({room_x:room,groups_x:groups});result.append('room_key','x');return result;}

test("partial room save retains successful operations for safe retry",async()=>{
  let fail=true, calls=0;
  const api=lib(async()=>{calls++;if(fail)throw Error('offline');return Response.json({id:9,room:'A',groups:[{identifier:'1'}]});});
  const saved=new Map(), rows=api.roomRowsInput(formWithRoom('A','1'));
  await assert.rejects(api.saveRoomRows('/rooms',rows,saved,()=>{}),/not fully saved/);
  fail=false;await api.saveRoomRows('/rooms',rows,saved,()=>{});await api.saveRoomRows('/rooms',rows,saved,()=>{});
  assert.equal(calls,2);assert.equal(saved.size,1);
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
        return expected.endsWith("/pdf") ? new Response(new Uint8Array([37,80,68,70,45,0,255]), {headers:{"content-type":"application/pdf","content-disposition":"attachment; filename=sample.pdf"}}) : Response.json({});
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
    ].flatMap((kind) => [["POST", `/7/documents/${kind}/preview`],["POST", `/7/documents/${kind}/pdf`]]),
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
    if(path.endsWith("/pdf")) { assert.equal(result.headers.get("content-disposition"),"attachment; filename=sample.pdf"); assert.deepEqual([...new Uint8Array(await result.arrayBuffer())],[37,80,68,70,45,0,255]); }
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

test("Add room and Remove edit draft rows without requests",()=>{
  const component=ui(()=>{throw Error('must not save');});
  const tree=component.Rooms({event:{rooms:[{id:1,room:'A',groups:[]}],event_type:'MIDTERM'},path:'/rooms',update:()=>{}});
  const buttons=nodes(tree).filter(n=>n.type==='button');
  const add=buttons.find(n=>n.props.children==='+ Add room');
  add.props.onClick();add.props.onClick();assert.equal(component.stateChanges.at(-1).length,3);
  buttons.find(n=>n.props.children==='Remove').props.onClick();assert.equal(component.stateChanges.at(-1).length,2);
  assert.equal(new Set(component.stateChanges.at(-1).map(row=>row.key)).size,2);
});

test("draft room identity keeps blank rows, edits and remaining values independent", () => {
  const event={rooms:[{id:1,room:'LE 12',groups:[{identifier:'2'}]}],event_type:'MIDTERM'};
  const props={event,path:'/rooms',update:()=>{}};
  const first=ui();const tree=first.Rooms(props);
  const inputs=nodes(tree).filter(n=>n.type==='input');
  assert.equal(inputs.find(n=>n.props.name==='room_saved-1').props.value,'LE 12');
  const add=nodes(tree).find(n=>n.type==='button' && n.props.children==='+ Add room');
  add.props.onClick();add.props.onClick();
  let rows=first.stateChanges.at(-1);
  assert.equal(new Set(rows.map(r=>r.key)).size,3);
  for(const row of rows.slice(1)) {assert.equal(row.room,'');assert.equal(row.groups,'');assert.match(row.key,/^draft-/);}
  const next=ui(undefined,'LECTURER',[rows]);const view=next.Rooms(props);
  const fields=nodes(view).filter(n=>n.type==='input');
  const room=fields.find(n=>n.props.name===`room_${rows[1].key}`);
  assert.equal(room.props.placeholder,undefined);assert.equal(room.props.value,'');
  assert.equal(fields.find(n=>n.props.name===`groups_${rows[1].key}`).props.placeholder,undefined);
  room.props.onChange({target:{value:'LE 99'}});
  rows=next.stateChanges.at(-1);assert.equal(rows[0].room,'LE 12');assert.equal(rows[1].room,'LE 99');assert.equal(rows[2].room,'');
  nodes(view).find(n=>n.type==='button' && n.props['aria-label']==='Remove room row 1').props.onClick();
  rows=next.stateChanges.at(-1);assert.equal(rows.length,2);assert.equal(rows[0].room,'LE 99');assert.equal(rows[1].room,'');
  const reordered=ui(undefined,'LECTURER',[[...rows].reverse()]).Rooms(props);
  const reorderedRows=nodes(reordered).filter(n=>n.props?.className==='room-assignment-row');
  assert.equal(reorderedRows[0].key,rows[1].key);assert.equal(reorderedRows[1].key,rows[0].key);
  const blank=formWithRoom('','');assert.equal(lib().roomRowsInput(blank).length,0);
  assert.throws(()=>lib().roomRowsInput(formWithRoom('LE 99','')),/Room row 1/);
  assert.ok(!JSON.stringify(lib().roomRowsInput(blank)).includes('e.g.'));
});

test("one keystroke updates only its controlled row and retains input identity",()=>{
  const props={event:{event_type:'MIDTERM',rooms:[{id:7,room:'',groups:[]},{id:8,room:'B',groups:[{identifier:'2'}]}]},path:'/rooms',update:()=>{}};
  const component=ui();const tree=component.Rooms(props);
  const input=nodes(tree).find(n=>n.props?.name==='room_saved-7');
  input.props.onChange({target:{value:'L'}});
  const rows=component.stateChanges.at(-1);assert.equal(rows[0].room,'L');assert.equal(rows[1].room,'B');
  const next=ui(undefined,'LECTURER',[rows]).Rooms(props);
  const before=nodes(tree).filter(n=>n.props?.className==='room-assignment-row');
  const after=nodes(next).filter(n=>n.props?.className==='room-assignment-row');
  assert.deepEqual(after.map(n=>n.key),before.map(n=>n.key));
  const updated=nodes(next).find(n=>n.props?.name==='room_saved-7');
  assert.equal(updated.type,input.type);assert.equal(updated.props.value,'L');
  assert.equal(updated.props.autoFocus,undefined);
  const groups=nodes(tree).find(n=>n.props?.name==='groups_saved-7');groups.props.onChange({target:{value:'1'}});
  assert.equal(component.stateChanges.at(-1)[0].groups,'1');
});

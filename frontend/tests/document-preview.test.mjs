import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";
import * as jsx from "react/jsx-runtime";
import { renderToStaticMarkup } from "react-dom/server";

function load(path, imports = {}, globals = {}) {
  const exports = {};
  const code = ts.transpileModule(
    readFileSync(new URL(`../src/${path}`, import.meta.url), "utf8"),
    {
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
        jsx: ts.JsxEmit.ReactJSX,
      },
    },
  ).outputText;
  vm.runInNewContext(code, {
    exports,
    require: (id) => imports[id],
    FormData,
    Error,
    AbortController,
    setTimeout,
    clearTimeout,
    ...globals,
  });
  return exports;
}
const assessments = load("lib/assessments.ts", {
  "./auth": {
    apiFetch: () => {
      throw Error("No real requests");
    },
  },
});
const preview = load("lib/document-preview.ts", {
  "./assessments": assessments,
});
function form(scope, values, dirty = true) {
  const data = new FormData();
  for (const [key, value] of Object.entries(values)) data.set(key, value);
  return { scope, values: data, dirty };
}
function samples() {
  return [
    form("metadata", {
      academic_year_start: "2030",
      term: "SPRING",
      display_label: "Unsaved term",
    }),
    form("event:ENDTERM", {
      venue: "Unsaved room",
      writing_start_time: "10:15",
      writing_end_time: "11:45",
    }),
    form("policy:ENDTERM", { maximum_score: "57", topics: "Unsaved topics" }),
    form("room:ENDTERM:new", { room: "Hall", groups: "1, 2" }),
  ];
}
const nodes = (node) =>
  !node || typeof node !== "object"
    ? []
    : [node, ...[node.props?.children].flat(Infinity).flatMap(nodes)];

test("draft snapshots current unsaved fields, policies, rooms and group deadlines", () => {
  const forms = samples();
  forms.push(
    form("event:COURSEWORK_HAND_IN", {
      submission_venue: "Default venue",
      deadline_group_0: "Lab A",
      deadline_date_0: "2031-05-01",
      deadline_venue_0: "Override",
    }),
  );
  const draft = preview.draftFromForms(forms);
  assert.equal(draft.metadata.display_label, "Unsaved term");
  assert.equal(draft.events[0].venue, "Unsaved room");
  assert.equal(draft.events[0].rooms[0].groups.length, 2);
  assert.equal(draft.policies[0].maximum_score, "57");
  assert.equal(draft.events[1].group_deadlines[0].venue, "Override");
  forms[1].values.set("venue", "Changed without Save");
  assert.equal(
    preview.draftFromForms(forms).events[0].venue,
    "Changed without Save",
  );
});

test("missing optional values stay null and unused new-room forms stay absent", () => {
  const forms = samples();
  forms[3] = form("room:ENDTERM:new", {});
  const draft = preview.draftFromForms(forms);
  assert.equal(draft.events[0].latest_arrival_time, null);
  assert.equal(draft.events[0].rooms.length, 0);
  assert.equal(draft.rules, undefined);
  forms[3].values.set("room", "Half filled");
  assert.throws(
    () => preview.draftFromForms(forms),
    /at least one practice group/,
  );
});

test("debounce reads latest values, aborts stale requests, and never saves", async () => {
  const timers = new Map();
  let serial = 0;
  const previewModule = load(
    "lib/document-preview.ts",
    { "./assessments": assessments },
    {
      setTimeout: (fn) => {
        timers.set(++serial, fn);
        return serial;
      },
      clearTimeout: (key) => timers.delete(key),
    },
  );
  const forms = samples(),
    updates = [],
    requests = [];
  const controller = previewModule.previewScheduler(
    () => preview.draftFromForms(forms),
    (draft, signal) =>
      new Promise((resolve) => requests.push({ draft, signal, resolve })),
    (state) => updates.push(state),
  );
  controller.schedule();
  forms[1].values.set("venue", "Latest");
  controller.schedule();
  assert.equal(timers.size, 1);
  let fn = [...timers.values()][0];
  timers.clear();
  const first = fn();
  assert.equal(requests[0].draft.events[0].venue, "Latest");
  controller.schedule();
  assert.equal(requests[0].signal.aborted, true);
  requests[0].resolve({ blocks: [], label: "stale" });
  await first;
  assert.ok(!updates.some((s) => s.preview?.label === "stale"));
  fn = [...timers.values()][0];
  timers.clear();
  const second = fn();
  requests[1].resolve({ blocks: [], label: "current" });
  await second;
  assert.equal(updates.at(-1).preview.label, "current");
  controller.dispose();
  assert.equal(requests[1].signal.aborted, true);
});

function component() {
  return load("components/document-preview.tsx", {
    "react/jsx-runtime": jsx,
    react: {
      useEffect: () => {},
      useRef: () => ({ current: null }),
      useState: (initial) => [initial, () => {}],
    },
    "@/lib/assessments": assessments,
    "@/lib/document-preview": preview,
  });
}
test("all seven selections leave the same editor children mounted", () => {
  const { DocumentWorkspace } = component();
  const child = jsx.jsx("input", { defaultValue: "Keep unsaved value" });
  const tree = DocumentWorkspace({ id: "1", children: () => child });
  const select = nodes(tree).find((n) => n.type === "nav");
  const options = nodes(select).filter((n) => n.type === "button");
  assert.equal(options.length, 7);
  for (const option of options)
    option.props.onClick();
  assert.ok(nodes(tree).includes(child));
  assert.equal(child.props.defaultValue, "Keep unsaved value");
});
test("AST rendering escapes user HTML and only permits known presentation nodes", () => {
  const { PreviewNodes } = component();
  const html = renderToStaticMarkup(
    jsx.jsx(PreviewNodes, {
      nodes: [
        {
          kind: "heading",
          level: 2,
          children: [{ kind: "text", text: "Heading" }],
        },
        { kind: "text", text: '<img src=x onerror="alert(1)">' },
        { kind: "script", text: "alert(1)" },
        {
          kind: "list",
          ordered: true,
          children: [
            { kind: "item", children: [{ kind: "text", text: "Item" }] },
          ],
        },
      ],
    }),
  );
  assert.ok(html.includes("&lt;img"));
  assert.ok(!html.includes("<img"));
  assert.ok(!html.includes("<script"));
  assert.ok(html.includes("<h2>"));
  assert.ok(html.includes("<ol>"));
});
test("responsive preview has independent scrolling and a stacked narrow layout", () => {
  const css = readFileSync(
    new URL("../src/app/globals.css", import.meta.url),
    "utf8",
  );
  assert.match(css, /\.document-workspace\s*\{[^}]*grid-template-columns:/);
  assert.match(css, /\.document-preview-pane\s*\{[^}]*position: sticky/s);
  assert.match(css, /@media \(max-width: 1100px\)/);
  assert.match(css, /\.document-preview-scroll\s*\{[^}]*overflow: auto/s);
});

test("modern workspace has accessible scrolling navigation and restrained preview surfaces", () => {
  const { DocumentWorkspace } = component();
  const tree = DocumentWorkspace({id: "1", children: () => null});
  const nav = nodes(tree).find(n => n.type === "nav");
  assert.equal(nav.props["aria-label"], "Assessment documents");
  const buttons = nodes(nav).filter(n => n.type === "button");
  assert.equal(buttons.length, 7);
  assert.equal(buttons.filter(n => n.props["aria-pressed"]).length, 1);
  assert.ok(buttons.every(n => n.props.type === "button"));
  const css = readFileSync(new URL("../src/app/globals.css", import.meta.url), "utf8");
  assert.match(css, /\.document-navigation\s*\{[^}]*flex-wrap: nowrap;[^}]*overflow-x: auto/s);
  assert.match(css, /\.document-navigation button:focus-visible/);
  assert.match(css, /\.draft-paper\s*\{[^}]*background: #fff;[^}]*font: inherit/s);
  assert.doesNotMatch(css.match(/\.draft-paper\s*\{[^}]*\}/s)[0], /box-shadow/);
  assert.match(css, /\.document-editor-pane \.assessment-form > fieldset > \.staff-actions\s*\{[^}]*position: sticky/s);
});

test("multiple unsaved room rows feed preview and removed rows disappear", () => {
  const forms=samples();
  const batch=form('rooms:ENDTERM',{room_a:'LE 23',groups_a:'2,3',room_b:'Hall',groups_b:'5'});
  batch.values.append('room_key','a');batch.values.append('room_key','b');forms.push(batch);
  assert.equal(preview.draftFromForms(forms).events[0].rooms.length,2);
  batch.values.set('room_a','Changed');
  assert.equal(preview.draftFromForms(forms).events[0].rooms[0].room,'Changed');
  batch.values.delete('room_key');batch.values.append('room_key','a');
  assert.equal(preview.draftFromForms(forms).events[0].rooms.length,1);
});
test("redundant explanatory text is absent while Draft Preview remains",()=>{
  const source=['assessment-editor.tsx','document-preview.tsx'].map(file=>readFileSync(new URL('../src/components/'+file,import.meta.url),'utf8')).join(' ').replace(/\s+/g,' ');
  for(const text of ['Uses the LaTeX document content.', 'Scheduled times are the official interval;', 'Separate identifiers with commas', 'Maximum and passing scores refer', 'Choose a document']) assert.ok(!source.includes(text),text);
  assert.ok(source.includes('Draft Preview'));
});

test("native input waits for React controlled commit before scheduling preview; cleanup cancels pending refresh", () => {
  const timers=new Map(), listeners=new Map(), changes=[];let next=0, effect, cleanup, scheduled=0;
  const element={querySelector:()=>null,addEventListener:(name,fn)=>listeners.set(name,fn),removeEventListener:name=>listeners.delete(name)};
  const loaded=load('components/document-preview.tsx',{
    'react/jsx-runtime':jsx,
    react:{useEffect:fn=>{effect=fn},useRef:()=>({current:element}),useState:initial=>[initial,value=>changes.push(value)]},
    '@/lib/assessments':assessments,
    '@/lib/document-preview':{...preview,previewScheduler:()=>({schedule:()=>scheduled++,dispose:()=>{}})},
  },{
    setTimeout:fn=>{timers.set(++next,fn);return next},clearTimeout:id=>timers.delete(id),
    MutationObserver:class {observe(){} disconnect(){}},
  });
  loaded.DocumentWorkspace({id:'1',children:()=>null});cleanup=effect();
  timers.clear();
  // A native input listener runs before the ancestor React change handler.
  listeners.get('input')();listeners.get('change')();
  assert.equal(changes.length,0);assert.equal(scheduled,0);assert.equal(timers.size,1);
  // React can now commit one character without an intervening preview render.
  [...timers.values()][0]();timers.clear();
  assert.equal(scheduled,1);
  listeners.get('input')();cleanup();assert.equal(timers.size,0);assert.equal(listeners.size,0);
});

test("PDF download sends unsaved snapshot for each document and releases blob URLs",async()=>{
  const requests=[],downloads=[],revoked=[];
  const helper=load('lib/assessment-pdf.ts',{'./auth':{apiFetch:async(path,init)=>{requests.push({path,init});return new Response('%PDF-1.7',{headers:{'content-type':'application/pdf'}})}}},{
    URL:{createObjectURL:()=> 'blob:test',revokeObjectURL:url=>revoked.push(url)},
    document:{body:{appendChild:()=>{}},createElement:()=>({click(){downloads.push(this.download)},remove(){}})},
    setTimeout:fn=>fn(),
  });
  const draft=preview.draftFromForms(samples());
  for(const kind of Object.keys(preview.documentLabels)) await helper.downloadAssessmentPdf('1',kind,draft);
  assert.equal(downloads.length,7);assert.equal(revoked.length,7);
  assert.equal(JSON.parse(requests[0].init.body).events[0].venue,'Unsaved room');
  assert.ok(requests.every(r=>r.path.endsWith('/pdf') && r.init.method==='POST'));
  const failed=load('lib/assessment-pdf.ts',{'./auth':{apiFetch:async()=>Response.json({detail:'Compiler busy'},{status:503})}});
  await assert.rejects(failed.downloadAssessmentPdf('1','DATES_OF_ASSESSMENTS',draft),/Compiler busy/);
});

test("Download PDF prevents duplicate clicks and reports errors without altering editor values",async()=>{
  let calls=0,reject, index=0;const updates=[];
  const helper=load('components/document-preview.tsx',{
    'react/jsx-runtime':jsx,
    react:{useEffect:()=>{},useRef:initial=>({current:index++===0?{}:initial}),useState:initial=>[initial,value=>updates.push(value)]},
    '@/lib/assessments':assessments,
    '@/lib/document-preview':{...preview,hasUnsavedDocumentChanges:()=>false,snapshotEditor:()=>({saved:'retained'})},
    '@/lib/assessment-pdf':{downloadAssessmentPdf:()=>{calls++;return new Promise((_,r)=>reject=r)}},
  });
  const tree=helper.DocumentWorkspace({id:'1',children:()=>null});
  const button=nodes(tree).find(n=>n.type==='button' && n.props.children==='Download PDF');
  const pending=button.props.onClick();await button.props.onClick();assert.equal(calls,1);
  reject(Error('Try again'));await pending;assert.ok(updates.includes('Try again'));assert.equal(updates.at(-1),false);
});

test('PDF guard compares values, allows reverts, and checks only relevant sections', () => {
  const forms = samples().map(sample => ({
    dataset: {previewScope: sample.scope, savedValues: preview.formValues(sample.values)},
    values: sample.values,
    querySelector: () => null,
  }));
  const module = load('lib/document-preview.ts', {'./assessments': assessments}, {
    FormData: class { constructor(form) { return form.values; } },
  });
  const editor = {querySelectorAll: () => forms};
  const dirty = () => module.hasUnsavedDocumentChanges(editor, 'ENDTERM_TEST_INFORMATION');
  assert.equal(dirty(), false);
  forms[1].values.set('venue', 'Edited');
  assert.equal(dirty(), true);
  assert.equal(module.hasUnsavedDocumentChanges(editor, 'MIDTERM_TEST_INFORMATION'), false);
  forms[1].values.set('venue', 'Unsaved room');
  assert.equal(dirty(), false);
  forms[1].querySelector = () => ({});
  assert.equal(dirty(), true); // Saving is not success.
});

test('Download PDF with unsaved values shows exact error without requesting or saving', async () => {
  let index = 0, calls = 0;
  const updates = [];
  const module = load('components/document-preview.tsx', {
    'react/jsx-runtime': jsx,
    react: {useEffect:()=>{},useRef:initial=>({current:index++===0?{}:initial}),useState:initial=>[initial,value=>updates.push(value)]},
    '@/lib/document-preview': {...preview, hasUnsavedDocumentChanges:()=>true, snapshotEditor:()=>{throw Error('Must not snapshot/download');}},
    '@/lib/assessment-pdf': {downloadAssessmentPdf:()=>{calls++;}},
  });
  const tree = module.DocumentWorkspace({id:'1',children:()=>null});
  await nodes(tree).find(n=>n.type==='button' && n.props.children==='Download PDF').props.onClick();
  assert.equal(calls,0);
  assert.deepEqual(updates,['You have unsaved changes. Please save your changes before downloading the PDF.']);
});

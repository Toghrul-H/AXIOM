import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

function library(path) {
  const source = readFileSync(new URL(path, import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText;
  const exports = {};
  vm.runInNewContext(compiled, { exports });
  return exports;
}

const truth = library("../src/lib/truth-table.ts");
const sets = library("../src/lib/set-operations.ts");
const plain = (value) => JSON.parse(JSON.stringify(value));
const ui = readFileSync(
  new URL("../src/components/course-visualizations.tsx", import.meta.url),
  "utf8",
);
const course = readFileSync(
  new URL("../src/components/course-workspace.tsx", import.meta.url),
  "utf8",
);

test("truth-table parser applies NOT, AND, OR, implication, and biconditional precedence", () => {
  const disjunction = truth.parseExpression("P ∨ Q ∧ R");
  assert.equal(disjunction.kind, "or");
  assert.equal(disjunction.right.kind, "and");
  const implication = truth.parseExpression("P -> Q -> R");
  assert.equal(implication.kind, "implies");
  assert.equal(implication.right.kind, "implies");
  const expression = truth.parseExpression("¬P ∧ (Q ↔ R)");
  assert.equal(
    truth.evaluate(expression, { P: false, Q: true, R: true }),
    true,
  );
  assert.equal(
    truth.evaluate(expression, { P: false, Q: true, R: false }),
    false,
  );
  assert.deepEqual(plain(truth.variables(expression)), ["P", "Q", "R"]);
  assert.deepEqual(plain(truth.truthAssignments(["P", "Q"])), [
    { P: true, Q: true },
    { P: true, Q: false },
    { P: false, Q: true },
    { P: false, Q: false },
  ]);
});

test("truth-table parser reports invalid input and protects against excessive rows", () => {
  assert.throws(
    () => truth.parseExpression("P ∧ )"),
    /Expected|Unexpected|Missing/,
  );
  assert.throws(() => truth.parseExpression("P @ Q"), /Unexpected character/);
  assert.throws(
    () => truth.truthAssignments(["A", "B", "C", "D", "E", "F", "G"]),
    /at most 6/,
  );
});

test("finite-set operations normalize duplicates deterministically", () => {
  const a = sets.parseFiniteSet("b, a, b\n c");
  const b = sets.parseFiniteSet("c, d, a");
  assert.deepEqual(plain(a), ["a", "b", "c"]);
  assert.deepEqual(plain(sets.parseFiniteSet(" , \n")), []);
  assert.deepEqual(plain(sets.operateSets(a, b, "union")), [
    "a",
    "b",
    "c",
    "d",
  ]);
  assert.deepEqual(plain(sets.operateSets(a, b, "intersection")), ["a", "c"]);
  assert.deepEqual(plain(sets.operateSets(a, b, "a-minus-b")), ["b"]);
  assert.deepEqual(plain(sets.operateSets(a, b, "symmetric-difference")), [
    "b",
    "d",
  ]);
  assert.deepEqual(plain(sets.vennRegions("intersection")), {
    left: false,
    middle: true,
    right: false,
  });
  assert.deepEqual(plain(sets.vennRegions("union")), {
    left: true,
    middle: true,
    right: true,
  });
  assert.deepEqual(plain(sets.vennRegions("a-minus-b")), {
    left: true,
    middle: false,
    right: false,
  });
  assert.deepEqual(plain(sets.vennRegions("b-minus-a")), {
    left: false,
    middle: false,
    right: true,
  });
  assert.deepEqual(plain(sets.vennRegions("symmetric-difference")), {
    left: true,
    middle: false,
    right: true,
  });
});

test("visualization UI exposes both accessible tools from Course", () => {
  for (const text of [
    "Truth Table Builder",
    "Set Operations Visualizer",
    "Build truth table",
    "Interactive visualizations",
    "Reset",
    "A minus B",
    "B minus A",
    "Symmetric difference",
  ])
    assert.match(ui, new RegExp(text));
  assert.match(course, /\/student\/course\/visualizations/);
  assert.match(ui, /role="img"/);
  assert.match(ui, /set-operation-card/);
  assert.match(ui, /set-operation-symbol/);
  assert.doesNotMatch(ui, /eval\(|Function\(/);
});

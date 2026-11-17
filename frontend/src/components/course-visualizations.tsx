"use client";

import { useMemo, useState } from "react";
import { RefreshCw } from "lucide-react";

import {
  evaluate,
  expressionLabel,
  parseExpression,
  subexpressions,
  truthAssignments,
  variables,
} from "@/lib/truth-table";
import {
  operateSets,
  parseFiniteSet,
  type SetOperation,
  vennRegions,
} from "@/lib/set-operations";

const truthExamples = ["¬(P ∧ Q) → R", "P ↔ (Q ∨ ¬R)", "P → Q → R"];
const setExamples = { a: "1, 2, 3, 4", b: "3, 4, 5" };
const symbol = (value: boolean) => (value ? "T" : "F");

export function CourseVisualizations() {
  return (
    <>
      <section className="visualization-intro panel">
        <p className="eyebrow">INTERACTIVE LEARNING</p>
        <h1>Interactive visualizations</h1>
        <p>
          Explore core Discrete Mathematics I ideas locally in your browser.
          These tools do not change your course progress or saved content.
        </p>
      </section>
      <TruthTableBuilder />
      <SetOperationsVisualizer />
    </>
  );
}

export function TruthTableBuilder() {
  const [source, setSource] = useState(truthExamples[0]);
  const [submitted, setSubmitted] = useState(source);
  const result = useMemo(() => {
    try {
      const expression = parseExpression(submitted);
      const names = variables(expression);
      return {
        expression,
        names,
        parts: subexpressions(expression),
        rows: truthAssignments(names),
        error: "",
      };
    } catch (error) {
      return {
        expression: null,
        names: [],
        parts: [],
        rows: [],
        error: error instanceof Error ? error.message : "Invalid expression.",
      };
    }
  }, [submitted]);
  const apply = () => setSubmitted(source);
  return (
    <section className="panel visualization-panel">
      <header>
        <div>
          <p className="eyebrow">LOGIC</p>
          <h2>Truth Table Builder</h2>
        </div>
        <button
          className="button button-quiet"
          onClick={() => {
            setSource(truthExamples[0]);
            setSubmitted(truthExamples[0]);
          }}
        >
          <RefreshCw size={16} />
          Reset
        </button>
      </header>
      <p>
        Use variables such as P and Q, NOT (¬), AND (∧), OR (∨), implication
        (→), biconditional (↔), and parentheses. At most six variables are
        allowed.
      </p>
      <label htmlFor="truth-expression">
        Propositional expression
        <input
          id="truth-expression"
          value={source}
          onChange={(event) => setSource(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") apply();
          }}
        />
      </label>
      <div className="visualization-actions">
        <button className="button button-primary" onClick={apply}>
          Build truth table
        </button>
        {truthExamples.map((example) => (
          <button
            key={example}
            className="button button-quiet"
            onClick={() => {
              setSource(example);
              setSubmitted(example);
            }}
          >
            {example}
          </button>
        ))}
      </div>
      {result.error ? (
        <div className="error-message" role="alert">
          {result.error}
        </div>
      ) : (
        <div className="truth-table-wrap" tabIndex={0}>
          <table className="truth-table">
            <thead>
              <tr>
                {result.names.map((name) => (
                  <th key={name} scope="col">
                    {name}
                  </th>
                ))}
                {result.parts.map((part) => (
                  <th key={expressionLabel(part)} scope="col">
                    {expressionLabel(part)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.rows.map((assignment, index) => (
                <tr key={index}>
                  {result.names.map((name) => (
                    <td key={name}>{symbol(assignment[name])}</td>
                  ))}
                  {result.parts.map((part) => (
                    <td key={expressionLabel(part)}>
                      {symbol(evaluate(part, assignment))}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

const operations: { value: SetOperation; label: string; notation: string }[] = [
  { value: "union", label: "Union", notation: "A ∪ B" },
  { value: "intersection", label: "Intersection", notation: "A ∩ B" },
  { value: "a-minus-b", label: "A minus B", notation: "A ∖ B" },
  { value: "b-minus-a", label: "B minus A", notation: "B ∖ A" },
  {
    value: "symmetric-difference",
    label: "Symmetric difference",
    notation: "A △ B",
  },
];

export function SetOperationsVisualizer() {
  const [aInput, setAInput] = useState(setExamples.a);
  const [bInput, setBInput] = useState(setExamples.b);
  const [operation, setOperation] = useState<SetOperation>("union");
  const a = useMemo(() => parseFiniteSet(aInput), [aInput]);
  const b = useMemo(() => parseFiniteSet(bInput), [bInput]);
  const result = useMemo(() => operateSets(a, b, operation), [a, b, operation]);
  const regions = vennRegions(operation);
  const selected = operations.find((item) => item.value === operation)!;
  return (
    <section className="panel visualization-panel">
      <header>
        <div>
          <p className="eyebrow">SETS</p>
          <h2>Set Operations Visualizer</h2>
        </div>
        <button
          className="button button-quiet"
          onClick={() => {
            setAInput(setExamples.a);
            setBInput(setExamples.b);
            setOperation("union");
          }}
        >
          <RefreshCw size={16} />
          Reset
        </button>
      </header>
      <p>
        Enter comma- or line-separated elements. Whitespace is ignored,
        comparisons are case-sensitive, duplicates are removed, and results are
        sorted deterministically.
      </p>
      <div className="set-inputs">
        <label htmlFor="set-a">
          Set A
          <textarea
            id="set-a"
            value={aInput}
            onChange={(event) => setAInput(event.target.value)}
          />
        </label>
        <label htmlFor="set-b">
          Set B
          <textarea
            id="set-b"
            value={bInput}
            onChange={(event) => setBInput(event.target.value)}
          />
        </label>
      </div>
      <fieldset className="set-operations">
        <legend>Operation</legend>
        {operations.map((item) => (
          <label key={item.value}>
            <input
              type="radio"
              name="set-operation"
              checked={operation === item.value}
              onChange={() => setOperation(item.value)}
            />
            {item.label}{" "}
            <span aria-label={item.notation}>({item.notation})</span>
          </label>
        ))}
      </fieldset>
      <div className="set-result">
        <div>
          <h3>{selected.notation}</h3>
          <p>{result.length ? `{${result.join(", ")}}` : "∅"}</p>
          <p className="muted">
            A = {`{${a.join(", ")}}`} · B = {`{${b.join(", ")}}`}
          </p>
        </div>
        <VennDiagram regions={regions} />
      </div>
    </section>
  );
}

function VennDiagram({ regions }: { regions: ReturnType<typeof vennRegions> }) {
  return (
    <svg
      className="venn-diagram"
      viewBox="0 0 300 190"
      role="img"
      aria-label="Two-set Venn diagram; highlighted regions are included in the chosen operation."
    >
      <circle
        className={regions.left ? "venn-selected" : "venn-region"}
        cx="115"
        cy="95"
        r="65"
      />
      <circle
        className={regions.right ? "venn-selected" : "venn-region"}
        cx="185"
        cy="95"
        r="65"
      />
      <ellipse
        className={regions.middle ? "venn-overlap-selected" : "venn-overlap"}
        cx="150"
        cy="95"
        rx="30"
        ry="65"
      />
      <text x="76" y="38">
        A
      </text>
      <text x="216" y="38">
        B
      </text>
    </svg>
  );
}

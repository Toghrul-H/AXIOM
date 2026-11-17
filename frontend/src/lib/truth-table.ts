export type TruthValue = boolean;
export type Expression =
  | { kind: "variable"; name: string }
  | { kind: "not"; value: Expression }
  | {
      kind: "and" | "or" | "implies" | "iff";
      left: Expression;
      right: Expression;
    };

type Token = {
  type: "variable" | "operator" | "left" | "right";
  value: string;
  offset: number;
};
const operators: Record<string, Expression["kind"]> = {
  "¬": "not",
  "!": "not",
  NOT: "not",
  "∧": "and",
  "&": "and",
  AND: "and",
  "∨": "or",
  "|": "or",
  OR: "or",
  "→": "implies",
  "->": "implies",
  "↔": "iff",
  "<->": "iff",
};

function tokens(source: string): Token[] {
  const result: Token[] = [];
  let index = 0;
  while (index < source.length) {
    const rest = source.slice(index);
    const whitespace = rest.match(/^\s+/);
    if (whitespace) {
      index += whitespace[0].length;
      continue;
    }
    const operator = rest.match(/^(<->|->|¬|!|∧|&|∨|\||→|↔)/);
    if (operator) {
      result.push({ type: "operator", value: operator[0], offset: index });
      index += operator[0].length;
      continue;
    }
    if (rest[0] === "(") {
      result.push({ type: "left", value: "(", offset: index++ });
      continue;
    }
    if (rest[0] === ")") {
      result.push({ type: "right", value: ")", offset: index++ });
      continue;
    }
    const name = rest.match(/^[A-Za-z][A-Za-z0-9_]*/);
    if (name) {
      const uppercase = name[0].toUpperCase();
      result.push(
        operators[uppercase]
          ? { type: "operator", value: uppercase, offset: index }
          : { type: "variable", value: name[0], offset: index },
      );
      index += name[0].length;
      continue;
    }
    throw new Error(`Unexpected character at position ${index + 1}.`);
  }
  return result;
}

class Parser {
  private index = 0;
  constructor(private readonly input: Token[]) {}
  parse() {
    if (!this.input.length)
      throw new Error("Enter a propositional expression.");
    const result = this.iff();
    if (this.peek())
      throw new Error(
        `Unexpected “${this.peek()!.value}” at position ${this.peek()!.offset + 1}.`,
      );
    return result;
  }
  private peek() {
    return this.input[this.index];
  }
  private take(value?: string) {
    const item = this.peek();
    if (item && (!value || item.value === value)) {
      this.index += 1;
      return item;
    }
    return undefined;
  }
  private iff(): Expression {
    let value = this.implies();
    while (this.take("↔") || this.take("<->"))
      value = { kind: "iff", left: value, right: this.implies() };
    return value;
  }
  private implies(): Expression {
    const left = this.or();
    if (this.take("→") || this.take("->"))
      return { kind: "implies", left, right: this.implies() };
    return left;
  }
  private or(): Expression {
    let value = this.and();
    while (this.take("∨") || this.take("|") || this.take("OR"))
      value = { kind: "or", left: value, right: this.and() };
    return value;
  }
  private and(): Expression {
    let value = this.not();
    while (this.take("∧") || this.take("&") || this.take("AND"))
      value = { kind: "and", left: value, right: this.not() };
    return value;
  }
  private not(): Expression {
    if (this.take("¬") || this.take("!") || this.take("NOT"))
      return { kind: "not", value: this.not() };
    if (this.take("(")) {
      const value = this.iff();
      if (!this.take(")")) throw new Error("Missing closing parenthesis.");
      return value;
    }
    const item = this.take();
    if (item?.type === "variable")
      return { kind: "variable", name: item.value };
    throw new Error(
      `Expected a variable, NOT, or “(”${item ? ` at position ${item.offset + 1}` : ""}.`,
    );
  }
}

export function parseExpression(source: string): Expression {
  return new Parser(tokens(source)).parse();
}
export function variables(expression: Expression): string[] {
  const result = new Set<string>();
  const visit = (item: Expression) => {
    if (item.kind === "variable") result.add(item.name);
    else if (item.kind === "not") visit(item.value);
    else {
      visit(item.left);
      visit(item.right);
    }
  };
  visit(expression);
  return [...result].sort();
}
export function expressionLabel(expression: Expression): string {
  if (expression.kind === "variable") return expression.name;
  if (expression.kind === "not")
    return `¬(${expressionLabel(expression.value)})`;
  const symbols = { and: "∧", or: "∨", implies: "→", iff: "↔" } as const;
  return `(${expressionLabel(expression.left)} ${symbols[expression.kind]} ${expressionLabel(expression.right)})`;
}
export function evaluate(
  expression: Expression,
  assignment: Record<string, TruthValue>,
): TruthValue {
  switch (expression.kind) {
    case "variable":
      return Boolean(assignment[expression.name]);
    case "not":
      return !evaluate(expression.value, assignment);
    case "and":
      return (
        evaluate(expression.left, assignment) &&
        evaluate(expression.right, assignment)
      );
    case "or":
      return (
        evaluate(expression.left, assignment) ||
        evaluate(expression.right, assignment)
      );
    case "implies":
      return (
        !evaluate(expression.left, assignment) ||
        evaluate(expression.right, assignment)
      );
    case "iff":
      return (
        evaluate(expression.left, assignment) ===
        evaluate(expression.right, assignment)
      );
  }
}
export function subexpressions(expression: Expression): Expression[] {
  const values: Expression[] = [];
  const seen = new Set<string>();
  const visit = (item: Expression) => {
    if (item.kind === "variable") return;
    if (item.kind === "not") visit(item.value);
    else {
      visit(item.left);
      visit(item.right);
    }
    const key = expressionLabel(item);
    if (!seen.has(key)) {
      seen.add(key);
      values.push(item);
    }
  };
  visit(expression);
  return values;
}
export function truthAssignments(
  names: string[],
  limit = 6,
): Record<string, TruthValue>[] {
  if (names.length > limit)
    throw new Error(`Use at most ${limit} propositional variables.`);
  const count = 2 ** names.length;
  return Array.from({ length: count }, (_, row) =>
    Object.fromEntries(
      names.map((name, index) => [
        name,
        Boolean(((count - row - 1) >> (names.length - index - 1)) & 1),
      ]),
    ),
  );
}

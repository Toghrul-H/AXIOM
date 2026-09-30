export type MathSymbol = {
  text: string;
  label: string;
  spacing?: boolean;
  pair?: readonly [string, string];
};
const symbol = (text: string, label: string, spacing = false): MathSymbol => ({
  text,
  label,
  spacing,
});
const pair = (left: string, right: string, label: string): MathSymbol => ({
  text: `${left} ${right}`,
  label,
  pair: [left, right],
});
const equal = symbol("=", "Equals", true),
  unequal = symbol("≠", "Not equal", true);
const member = symbol("∈", "Element of", true),
  notMember = symbol("∉", "Not an element of", true);
const arrow = symbol("→", "Right arrow", true),
  iff = symbol("↔", "If and only if", true);
const all = symbol("∀", "For all"),
  exists = symbol("∃", "There exists");
const and = symbol("∧", "Logical and", true),
  or = symbol("∨", "Logical or", true),
  not = symbol("¬", "Logical not");
const subset = symbol("⊆", "Subset or equal", true),
  product = symbol("×", "Cartesian product or multiplication", true);
const parentheses = pair("(", ")", "Parentheses"),
  braces = pair("{", "}", "Braces");
export const LOGIC_SYMBOLS = [
  not,
  and,
  or,
  arrow,
  iff,
  all,
  exists,
  symbol("⊤", "True"),
  symbol("⊥", "False"),
  equal,
  unequal,
  parentheses,
];
export const SET_SYMBOLS = [
  symbol("∪", "Union", true),
  symbol("∩", "Intersection", true),
  symbol("∖", "Set difference", true),
  member,
  notMember,
  subset,
  symbol("⊂", "Proper subset", true),
  symbol("⊇", "Superset or equal", true),
  symbol("⊃", "Proper superset", true),
  symbol("∅", "Empty set"),
  product,
  equal,
  unequal,
  braces,
  parentheses,
];
export const RELATION_SYMBOLS = [
  member,
  notMember,
  product,
  symbol("∘", "Composition", true),
  symbol("⁻¹", "Inverse"),
  arrow,
  symbol("↦", "Maps to", true),
  symbol("²", "Squared"),
  equal,
  unequal,
  subset,
  all,
  exists,
  and,
  or,
  not,
  braces,
  parentheses,
];
export const COMPLEX_SYMBOLS = [
  symbol("i", "Imaginary unit"),
  symbol("π", "Pi"),
  symbol("√", "Square root"),
  symbol("±", "Plus or minus", true),
  equal,
  unequal,
  pair("|", "|", "Absolute value bars"),
  symbol("arg", "Argument"),
  symbol("e", "Euler’s number"),
  symbol("°", "Degrees"),
  parentheses,
];
export const COMBINATORICS_SYMBOLS = [
  symbol("!", "Factorial"),
  symbol("Σ", "Summation"),
  symbol("∏", "Product"),
  symbol("+", "Plus", true),
  symbol("−", "Minus", true),
  product,
  equal,
  parentheses,
  braces,
];
export const GRAPH_SYMBOLS = [
  member,
  notMember,
  equal,
  unequal,
  symbol("≤", "Less than or equal", true),
  symbol("≥", "Greater than or equal", true),
  arrow,
  iff,
  braces,
  parentheses,
];
export const GENERAL_SYMBOLS = [
  equal,
  unequal,
  symbol("≤", "Less than or equal", true),
  symbol("≥", "Greater than or equal", true),
  parentheses,
];
export const MATH_PROFILES = {
  logic: { label: "Logic", symbols: LOGIC_SYMBOLS },
  sets: { label: "Sets", symbols: SET_SYMBOLS },
  relations: { label: "Relations / Functions", symbols: RELATION_SYMBOLS },
  complex: { label: "Complex Numbers", symbols: COMPLEX_SYMBOLS },
  combinatorics: { label: "Combinatorics", symbols: COMBINATORICS_SYMBOLS },
  graphs: { label: "Graphs", symbols: GRAPH_SYMBOLS },
  general: { label: "General", symbols: GENERAL_SYMBOLS },
};
export type MathProfile = keyof typeof MATH_PROFILES;
const topicProfiles: Record<string, MathProfile> = {
  logic: "logic",
  sets: "sets",
  "binary-relations": "relations",
  functions: "relations",
  "complex-numbers": "complex",
  combinatorics: "combinatorics",
  graphs: "graphs",
};
export function mathProfileForTopic(slug?: string | null): MathProfile {
  return slug && Object.hasOwn(topicProfiles, slug)
    ? topicProfiles[slug]
    : "general";
}
// New question-specific symbols can be supplied without changing quiz-page logic.
export function symbolsForProfile(
  profile: MathProfile,
  extras: readonly MathSymbol[] = [],
): MathSymbol[] {
  return [
    ...new Map(
      [...MATH_PROFILES[profile].symbols, ...extras].map((s) => [s.text, s]),
    ).values(),
  ];
}
export function insertMathSymbol(
  value: string,
  start: number,
  end: number,
  s: MathSymbol,
  maxLength: number,
) {
  const before = value.slice(0, start),
    after = value.slice(end),
    selected = value.slice(start, end);
  let inserted: string, cursor: number;
  if (s.pair) {
    inserted = s.pair[0] + selected + s.pair[1];
    cursor = start + s.pair[0].length + selected.length;
  } else {
    const left = s.spacing && before && !/\s$/.test(before) ? " " : "";
    const right = s.spacing && !/^\s/.test(after) ? " " : "";
    inserted = left + s.text + right;
    cursor = start + inserted.length;
  }
  const text = before + inserted + after;
  return text.length > maxLength ? null : { text, cursor };
}

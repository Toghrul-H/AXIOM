export type SetOperation =
  "union" | "intersection" | "a-minus-b" | "b-minus-a" | "symmetric-difference";
const compare = (left: string, right: string) =>
  left < right ? -1 : left > right ? 1 : 0;

export function parseFiniteSet(input: string): string[] {
  return [
    ...new Set(
      input
        .split(/[\n,]/)
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  ].sort(compare);
}
export function operateSets(
  a: string[],
  b: string[],
  operation: SetOperation,
): string[] {
  const left = new Set(a);
  const right = new Set(b);
  const union = [...new Set([...a, ...b])];
  const selected =
    operation === "union"
      ? union
      : operation === "intersection"
        ? a.filter((item) => right.has(item))
        : operation === "a-minus-b"
          ? a.filter((item) => !right.has(item))
          : operation === "b-minus-a"
            ? b.filter((item) => !left.has(item))
            : union.filter((item) => left.has(item) !== right.has(item));
  return selected.sort(compare);
}
export function vennRegions(operation: SetOperation) {
  return {
    left:
      operation === "union" ||
      operation === "a-minus-b" ||
      operation === "symmetric-difference",
    middle: operation === "union" || operation === "intersection",
    right:
      operation === "union" ||
      operation === "b-minus-a" ||
      operation === "symmetric-difference",
  };
}

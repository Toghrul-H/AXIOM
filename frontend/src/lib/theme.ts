export const APPEARANCE_STORAGE_KEY = "axiom-appearance";

export type AppearancePreference = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

export function normalizeAppearance(value: unknown): AppearancePreference {
  return value === "light" || value === "dark" || value === "system"
    ? value
    : "system";
}

export function resolveTheme(
  preference: AppearancePreference,
  systemDark: boolean,
): ResolvedTheme {
  return preference === "system" ? (systemDark ? "dark" : "light") : preference;
}

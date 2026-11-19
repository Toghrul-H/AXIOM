"use client";

import { useEffect, useId, useState } from "react";
import {
  APPEARANCE_STORAGE_KEY,
  normalizeAppearance,
  resolveTheme,
  type AppearancePreference,
} from "@/lib/theme";

function applyAppearance(
  preference: AppearancePreference,
  systemDark: boolean,
) {
  const theme = resolveTheme(preference, systemDark);
  document.documentElement.dataset.theme = theme;
  document.documentElement.dataset.themePreference = preference;
  document.documentElement.style.colorScheme = theme;
}

export function ThemePreference() {
  const id = useId();
  const [preference, setPreference] = useState<AppearancePreference>(() =>
    typeof window === "undefined"
      ? "system"
      : normalizeAppearance(
          window.localStorage.getItem(APPEARANCE_STORAGE_KEY),
        ),
  );

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    applyAppearance(preference, media.matches);
    const onChange = () => {
      if (preference === "system") applyAppearance(preference, media.matches);
    };
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [preference]);

  function update(value: string) {
    const next = normalizeAppearance(value);
    window.localStorage.setItem(APPEARANCE_STORAGE_KEY, next);
    setPreference(next);
    applyAppearance(
      next,
      window.matchMedia("(prefers-color-scheme: dark)").matches,
    );
  }

  return (
    <label className="theme-preference" htmlFor={id}>
      <span>Appearance</span>
      <select
        id={id}
        value={preference}
        onChange={(event) => update(event.target.value)}
      >
        <option value="system">System</option>
        <option value="light">Light</option>
        <option value="dark">Dark</option>
      </select>
    </label>
  );
}

"use client";
import { useEffect, useState } from "react";
import { apiFetch } from "./auth";
import type { ProgressData } from "./progress";
export function useProgress() {
  const [data, setData] = useState<ProgressData | null>(null);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const response = await apiFetch("/student/progress/me", {
          signal: controller.signal,
        });
        if (!response.ok)
          throw new Error(
            "Progress data could not be loaded. Please try again.",
          );
        const result: ProgressData = await response.json();
        if (!controller.signal.aborted) setData(result);
      } catch {
        if (!controller.signal.aborted)
          setError("Progress data could not be loaded. Please try again.");
      }
    }
    void load();
    return () => controller.abort();
  }, [revision]);
  function retry() {
    setData(null);
    setError("");
    setRevision((r) => r + 1);
  }
  return { data, error, retry };
}

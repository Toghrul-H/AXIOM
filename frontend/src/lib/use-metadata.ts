"use client";
import { useEffect, useState } from "react";
import { Metadata, questionsApi, Topic } from "./questions";

export function useMetadata() {
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    questionsApi
      .metadata(controller.signal)
      .then(setMetadata)
      .catch((e: Error) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => controller.abort();
  }, []);
  return { metadata, error };
}

export function orderedTopics(
  topics: Topic[],
): { topic: Topic; label: string }[] {
  const byId = new Map(topics.map((t) => [t.id, t]));
  function path(topic: Topic): string {
    const names = [topic.name];
    const seen = new Set([topic.id]);
    let parent =
      topic.parent_id === null ? undefined : byId.get(topic.parent_id);
    while (parent && !seen.has(parent.id)) {
      seen.add(parent.id);
      names.unshift(parent.name);
      parent =
        parent.parent_id === null ? undefined : byId.get(parent.parent_id);
    }
    return names.join(" / ");
  }
  const sorted: Topic[] = [];
  const visited = new Set<number>();
  function visit(parent: number | null) {
    for (const t of topics
      .filter((t) => t.parent_id === parent)
      .sort((a, b) => a.sort_order - b.sort_order || a.id - b.id)) {
      if (visited.has(t.id)) continue;
      visited.add(t.id);
      sorted.push(t);
      visit(t.id);
    }
  }
  visit(null);
  for (const t of topics) if (!visited.has(t.id)) sorted.push(t);
  return sorted.map((topic) => ({ topic, label: path(topic) }));
}

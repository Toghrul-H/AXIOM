"use client";
import { useState } from "react";
import { Metadata, QuestionFilters as Filters } from "@/lib/questions";
import { orderedTopics } from "@/lib/use-metadata";

export function QuestionFilters({
  metadata,
  onApply,
}: {
  metadata: Metadata;
  onApply: (filters: Filters) => void;
}) {
  const [draft, setDraft] = useState<Filters>({});
  function set(key: keyof Filters, value: string) {
    setDraft({ ...draft, [key]: value });
  }
  return (
    <form
      className="panel filters-panel"
      onSubmit={(e) => {
        e.preventDefault();
        onApply(draft);
      }}
      aria-label="Question filters"
    >
      <div className="filters-grid">
        <div className="field">
          <label htmlFor="filter-search">Search question text / title</label>
          <input
            id="filter-search"
            maxLength={200}
            value={draft.q ?? ""}
            onChange={(e) => set("q", e.target.value)}
            placeholder="Search…"
          />
        </div>
        <div className="field">
          <label htmlFor="filter-topic">Topic / subtopic</label>
          <select
            id="filter-topic"
            value={draft.topic_id ?? ""}
            onChange={(e) => set("topic_id", e.target.value)}
          >
            <option value="">All topics</option>
            {orderedTopics(metadata.topics).map(({ topic, label }) => (
              <option key={topic.id} value={topic.id}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="filter-ps">Problem set</label>
          <select
            id="filter-ps"
            value={draft.problem_set_id ?? ""}
            onChange={(e) => set("problem_set_id", e.target.value)}
          >
            <option value="">All problem sets</option>
            {metadata.problem_sets.map((p) => (
              <option key={p.id} value={p.id}>
                {p.code}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="filter-difficulty">Difficulty</label>
          <select
            id="filter-difficulty"
            value={draft.difficulty ?? ""}
            onChange={(e) => set("difficulty", e.target.value)}
          >
            <option value="">All difficulties</option>
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="filter-response">Response type</label>
          <select
            id="filter-response"
            value={draft.response_type ?? ""}
            onChange={(e) => set("response_type", e.target.value)}
          >
            <option value="">All response types</option>
            {metadata.response_types.map((r) => (
              <option key={r.code} value={r.code}>
                {r.label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="filter-skill">Skill type</label>
          <select
            id="filter-skill"
            value={draft.skill_type ?? ""}
            onChange={(e) => set("skill_type", e.target.value)}
          >
            <option value="">All skills</option>
            {metadata.skill_types.map((s) => (
              <option key={s.code} value={s.code}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="filter-suitability">Assessment suitability</label>
          <select
            id="filter-suitability"
            value={draft.assessment_suitability ?? ""}
            onChange={(e) => set("assessment_suitability", e.target.value)}
          >
            <option value="">All suitability tags</option>
            {metadata.assessment_suitabilities.map((tag) => (
              <option key={tag.code} value={tag.code}>
                {tag.label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="filter-active">Status</label>
          <select
            id="filter-active"
            value={draft.is_active ?? ""}
            onChange={(e) => set("is_active", e.target.value)}
          >
            <option value="">Active and inactive</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
        </div>
      </div>
      <div className="filter-actions">
        <span className="field-hint">
          Filters combine. A parent topic includes its subtopics.
        </span>
        <button
          type="button"
          className="button button-secondary"
          onClick={() => {
            setDraft({});
            onApply({});
          }}
        >
          Clear filters
        </button>
        <button type="submit" className="button button-primary">
          Apply filters
        </button>
      </div>
    </form>
  );
}

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { learningApi, type PracticeTopic } from "@/lib/learning";
import { PageHeading } from "./page-heading";

export function PracticeHub() {
  const router = useRouter();
  const [topics, setTopics] = useState<PracticeTopic[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [count, setCount] = useState(3);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const receiveTopics = (rows: PracticeTopic[]) => {
    setTopics(rows);
    setSelected(
      (current) =>
        current ??
        rows.find((row) => row.available_question_count > 0)?.slug ??
        null,
    );
  };
  useEffect(() => {
    let live = true;
    learningApi
      .topics()
      .then((rows) => {
        if (live) receiveTopics(rows);
      })
      .catch((reason: Error) => {
        if (live) setError(reason.message);
      });
    return () => {
      live = false;
    };
  }, []);
  function retry() {
    setError("");
    learningApi
      .topics()
      .then(receiveTopics)
      .catch((reason: Error) => setError(reason.message));
  }
  const topic = topics?.find((row) => row.slug === selected) ?? null;
  async function start() {
    if (!topic) return;
    setBusy(true);
    setError("");
    try {
      const attempt = await learningApi.start(
        topic.slug,
        Math.min(count, topic.available_question_count),
      );
      router.push(`/student/quizzes/attempts/${attempt.id}`);
    } catch (reason) {
      setError((reason as Error).message);
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="YOUR LEARNING"
        title="Topic practice"
        description="Choose a topic for a private practice session. Your answers are saved to your account."
      />
      {error && (
        <p className="error-message" role="alert">
          {error}{" "}
          <button className="button button-quiet" onClick={retry}>
            Retry
          </button>
        </p>
      )}
      {!topics ? (
        <p role="status">Loading practice topics…</p>
      ) : (
        <>
          <div className="practice-grid" aria-label="Practice topics">
            {topics.map((row) => (
              <button
                type="button"
                key={row.slug}
                className={`panel practice-topic ${selected === row.slug ? "selected" : ""}`}
                onClick={() =>
                  row.available_question_count && setSelected(row.slug)
                }
                disabled={!row.available_question_count}
              >
                <strong>{row.name}</strong>
                <span>
                  {row.available_question_count
                    ? `${row.available_question_count} curated questions`
                    : "No curated questions yet"}
                </span>
                <small>
                  {row.attempted_question_count} answered ·{" "}
                  {row.pending_grading_count
                    ? `${row.pending_grading_count} awaiting grading`
                    : "No pending grading"}
                </small>
              </button>
            ))}
          </div>
          {topic ? (
            <section className="panel practice-start">
              <div>
                <h2>Practice {topic.name}</h2>
                <p>
                  Questions are selected from this topic. Free-response work is
                  reviewed by staff after submission.
                </p>
              </div>
              <label>
                Questions
                <select
                  value={count}
                  onChange={(event) => setCount(Number(event.target.value))}
                >
                  {[1, 2, 3, 4, 5]
                    .filter((value) => value <= topic.available_question_count)
                    .map((value) => (
                      <option key={value} value={value}>
                        {value} question{value === 1 ? "" : "s"}
                      </option>
                    ))}
                </select>
              </label>
              <button
                className="button button-primary"
                disabled={busy}
                onClick={start}
              >
                {busy ? "Creating practice…" : "Start practice"}
              </button>
            </section>
          ) : (
            <p className="empty-inline">
              No topic currently has enough curated questions for a practice
              session.
            </p>
          )}
        </>
      )}
    </>
  );
}

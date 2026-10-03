"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  gradingRequest,
  type Queue,
  type GradingAttempt,
  type GradedItem,
} from "@/lib/manual-grading";
import { PageHeading } from "./page-heading";
export function GradingQueue() {
  const [data, setData] = useState<Queue | null>(null),
    [error, setError] = useState(""),
    [status, setStatus] = useState("pending"),
    [offset, setOffset] = useState(0),
    [revision, setRevision] = useState(0);
  function reload() {
    setData(null);
    setError("");
    setRevision((r) => r + 1);
  }
  useEffect(() => {
    const abort = new AbortController();
    gradingRequest<Queue>(`?status=${status}&offset=${offset}&limit=20`, {
      signal: abort.signal,
    })
      .then(setData)
      .catch((e) => {
        if (!abort.signal.aborted) setError(e.message);
      });
    return () => abort.abort();
  }, [status, offset, revision]);
  return (
    <>
      <PageHeading
        eyebrow="TEACHING WORKSPACE"
        title="Manual Grading"
        description="Review submitted written responses using their original question snapshots."
      />
      <div className="panel quiz-panel">
        <label htmlFor="grading-status">Show </label>
        <select
          id="grading-status"
          value={status}
          onChange={(e) => {
            setData(null);
            setError("");
            setOffset(0);
            setStatus(e.target.value);
          }}
        >
          <option value="pending">Awaiting grading</option>
          <option value="completed">Completed</option>
          <option value="all">All manual work</option>
        </select>
        <button className="button button-secondary" onClick={reload}>
          Refresh
        </button>
      </div>
      {error ? (
        <div className="error-message" role="alert">
          {error}{" "}
          <button className="button button-secondary" onClick={reload}>
            Retry
          </button>
        </div>
      ) : !data ? (
        <p role="status">Loading grading queue…</p>
      ) : (
        <>
          {!data.items.length ? (
            <p className="panel empty-inline">
              {status === "pending"
                ? "There are currently no submitted written answers requiring manual grading on this page."
                : "No submitted attempts match this filter on this page."}
            </p>
          ) : (
            <div className="activity-list">
              {data.items.map((a) => (
                <Link
                  className="activity-row"
                  key={a.attempt_id}
                  href={`/teacher/grading/${a.attempt_id}`}
                >
                  <span>
                    <strong>{a.quiz_title}</strong>
                    <small>
                      {a.student.email} ·{" "}
                      {new Date(a.submitted_at).toLocaleString("en-GB")}
                    </small>
                    <small>
                      {a.pending_count} / {a.manual_answer_count} awaiting
                      grading · {a.grading_status}
                    </small>
                  </span>
                  <span>
                    {a.pending_count === 0
                      ? "Review / re-grade"
                      : a.pending_count < a.manual_answer_count
                        ? "Continue grading"
                        : "Grade"}{" "}
                    →
                  </span>
                </Link>
              ))}
            </div>
          )}
          <div className="quiz-actions">
            <button
              className="button button-secondary"
              disabled={offset === 0}
              onClick={() => {
                setData(null);
                setOffset(Math.max(0, offset - 20));
              }}
            >
              Previous
            </button>
            <span>{data.total} matching attempts</span>
            <button
              className="button button-secondary"
              disabled={offset + 20 >= data.total}
              onClick={() => {
                setData(null);
                setOffset(offset + 20);
              }}
            >
              Next
            </button>
          </div>
        </>
      )}
    </>
  );
}
export function AttemptGrading({ id }: { id: string }) {
  const [data, setData] = useState<GradingAttempt | null>(null),
    [error, setError] = useState(""),
    [revision, setRevision] = useState(0);
  useEffect(() => {
    const abort = new AbortController();
    gradingRequest<GradingAttempt>("/" + encodeURIComponent(id), {
      signal: abort.signal,
    })
      .then(setData)
      .catch((e) => {
        if (!abort.signal.aborted) setError(e.message);
      });
    return () => abort.abort();
  }, [id, revision]);
  return (
    <>
      <PageHeading
        eyebrow="MANUAL GRADING"
        title={data?.quiz_title ?? "Attempt grading"}
        description={
          data
            ? `${data.student.email} · Submitted ${new Date(data.submitted_at!).toLocaleString("en-GB")}`
            : "Historical submitted work"
        }
      />
      <Link className="text-link" href="/teacher/grading">
        ← Back to grading queue
      </Link>
      {error ? (
        <div className="error-message" role="alert">
          {error}
          <button
            className="button button-secondary"
            onClick={() => {
              setError("");
              setRevision((r) => r + 1);
            }}
          >
            Retry
          </button>
        </div>
      ) : !data ? (
        <p role="status">Loading submitted attempt…</p>
      ) : (
        <div className="quiz-list">
          {data.items
            .filter((i) => i.response_type === "FREE_RESPONSE")
            .map((item) => (
              <GradeForm key={item.id} attemptId={id} item={item} />
            ))}
        </div>
      )}
    </>
  );
}
function GradeForm({
  attemptId,
  item,
}: {
  attemptId: string;
  item: GradedItem;
}) {
  const [saved, setSaved] = useState(item),
    [score, setScore] = useState(
      item.manual_points === null ? "" : String(item.manual_points),
    ),
    [feedback, setFeedback] = useState(item.manual_feedback ?? ""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const saving = useRef(false);
  const blank = !(item.free_response ?? "").trim();
  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (saving.current) return;
    setNotice("");
    setError("");
    const points = Number(score);
    if (
      score.trim() === "" ||
      !Number.isInteger(points) ||
      points < 0 ||
      points > item.points ||
      (blank && points !== 0)
    ) {
      setError(
        blank
          ? "Blank responses require an explicit score of zero."
          : `Enter a whole number from 0 to ${item.points}.`,
      );
      return;
    }
    saving.current = true;
    setBusy(true);
    try {
      const result = await gradingRequest<GradingAttempt>(
        `/${encodeURIComponent(attemptId)}/answers/${item.id}`,
        {
          method: "PUT",
          body: JSON.stringify({ points, feedback: feedback.trim() || null }),
        },
      );
      const updated = result.items.find((i) => i.id === item.id);
      if (!updated)
        throw new Error(
          "Saved response could not be confirmed. Reload this attempt.",
        );
      setSaved(updated);
      setScore(String(updated.manual_points));
      setFeedback(updated.manual_feedback ?? "");
      setNotice("Grade saved.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to save grade.");
    } finally {
      saving.current = false;
      setBusy(false);
    }
  }
  return (
    <article className="panel quiz-panel">
      <span className="development-label">{saved.manual_grading_status}</span>
      <h2 className="quiz-question">{item.question_text}</h2>
      <h3>Student response</h3>
      <p className="quiz-question">
        {blank ? "No written response submitted." : item.free_response}
      </p>
      <details className="solution">
        <summary>Reference answer and explanation</summary>
        <div>
          <p className="quiz-question">
            {item.expected_answer ?? "No reference answer provided."}
          </p>
          {item.explanation && (
            <p className="quiz-question">{item.explanation}</p>
          )}
        </div>
      </details>
      {saved.manual_points !== null && (
        <p>
          Saved score: {saved.manual_points} / {item.points} ·{" "}
          {saved.graded_at && new Date(saved.graded_at).toLocaleString("en-GB")}
        </p>
      )}
      <form onSubmit={save}>
        <fieldset disabled={busy}>
          <legend className="sr-only">Grade written answer</legend>
          <div className="field">
            <label htmlFor={`score-${item.id}`}>Score / {item.points}</label>
            <input
              id={`score-${item.id}`}
              type="number"
              required
              min={0}
              max={blank ? 0 : item.points}
              step={1}
              value={score}
              onChange={(e) => {
                setScore(e.target.value);
                setNotice("");
              }}
            />
          </div>
          <div className="field">
            <label htmlFor={`feedback-${item.id}`}>Feedback (optional)</label>
            <textarea
              id={`feedback-${item.id}`}
              maxLength={20000}
              rows={4}
              value={feedback}
              onChange={(e) => {
                setFeedback(e.target.value);
                setNotice("");
              }}
            />
          </div>
          <button className="button button-primary" type="submit">
            {busy
              ? "Saving…"
              : saved.manual_points === null
                ? "Save Grade"
                : "Update Grade"}
          </button>
        </fieldset>
      </form>
      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="success-message" role="status">
          {notice}
        </p>
      )}
    </article>
  );
}

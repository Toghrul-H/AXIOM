"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { quizzesApi, QuizSummary, AttemptSummary } from "@/lib/quizzes";
import { PageHeading } from "./page-heading";

export function QuizList({ historyOnly = false }: { historyOnly?: boolean }) {
  const router = useRouter();
  const [quizzes, setQuizzes] = useState<QuizSummary[] | null>(null);
  const [attempts, setAttempts] = useState<AttemptSummary[]>([]);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const quizRows = quizzes ?? [];
  useEffect(() => {
    let live = true;
    Promise.all([
      historyOnly ? Promise.resolve([]) : quizzesApi.list(),
      quizzesApi.history(offset),
    ])
      .then(([q, a]) => {
        if (live) {
          setQuizzes(q);
          setAttempts(a);
        }
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [offset, historyOnly]);
  async function start(id: number) {
    setBusy(true);
    setError("");
    try {
      const a = await quizzesApi.start(id);
      router.push(`/student/quizzes/attempts/${a.id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="YOUR LEARNING"
        title={historyOnly ? "Learning history" : "Quizzes"}
        description={
          historyOnly
            ? "Review submitted work, grading status, and saved practice sessions."
            : "Choose a quiz, work through the questions, then review every answer after finishing."
        }
      />
      {!historyOnly && (
        <p className="quiz-notice">
          Your attempts are saved to your account. Sign in to resume them on
          another device.
        </p>
      )}
      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}
      {!historyOnly && !quizzes ? (
        <p role="status">Loading quizzes…</p>
      ) : (
        !historyOnly && (
          <div className="quiz-list">
            {quizRows.map((q) => (
              <article className="panel quiz-panel" key={q.id}>
                <h2>{q.title}</h2>
                <p>{q.description}</p>
                <p>
                  {q.question_count} questions · {q.objective_points}{" "}
                  automatically gradable points · Available
                </p>
                <button
                  disabled={busy}
                  className="button button-primary"
                  onClick={() => start(q.id)}
                  aria-label={`Start ${q.title}`}
                >
                  Start Quiz
                </button>
              </article>
            ))}
            {quizRows.length === 0 && <p>No quizzes are available yet.</p>}
          </div>
        )
      )}
      <h2 className="quiz-section-title">
        {historyOnly ? "Your activity" : "Your quiz attempts"}
      </h2>
      <div className="quiz-list">
        {attempts.map((a) => (
          <article className="panel quiz-panel" key={a.id}>
            <h3>{a.quiz_title}</h3>
            <p>
              {new Date(a.started_at).toLocaleString()} ·{" "}
              {a.status === "IN_PROGRESS"
                ? "In progress"
                : a.objective_total
                  ? `Automatically graded points: ${a.objective_score} / ${a.objective_total}`
                  : "Written responses · not automatically graded"}
              {a.status === "SUBMITTED" &&
                a.manual_answer_count > 0 &&
                ` · ${a.grading_status === "GRADED" ? "Manual grading complete" : a.grading_status === "PARTIALLY_GRADED" ? `${a.pending_grading_count} response${a.pending_grading_count === 1 ? "" : "s"} awaiting grading` : "Awaiting manual grading"}`}
            </p>
            <Link
              className="button button-secondary"
              href={`/student/quizzes/attempts/${a.id}${a.status === "SUBMITTED" ? "/results" : ""}`}
            >
              {a.status === "IN_PROGRESS"
                ? "Resume quiz"
                : "View results and review"}
            </Link>
          </article>
        ))}
      </div>
      {attempts.length === 0 && <p>No attempts on this page.</p>}
      <div className="quiz-actions">
        <button
          className="button button-secondary"
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - 20))}
        >
          Newer attempts
        </button>
        <button
          className="button button-secondary"
          disabled={attempts.length < 20}
          onClick={() => setOffset(offset + 20)}
        >
          Older attempts
        </button>
      </div>
    </>
  );
}

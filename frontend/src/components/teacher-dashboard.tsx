"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Question, questionsApi, typeLabels } from "@/lib/questions";
import { quizRequest, type StaffQuiz } from "@/lib/quizzes";
import { PageHeading } from "./page-heading";
export function TeacherDashboard() {
  const [data, setData] = useState<{
    questions: Question[];
    quizzes: StaffQuiz[];
  } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    const controller = new AbortController();
    async function loadQuestions() {
      const questions: Question[] = [];
      for (let offset = 0; ; offset += 100) {
        const page = await questionsApi.list(offset, 100, controller.signal);
        questions.push(...page.items);
        if (offset + page.items.length >= page.total || !page.items.length)
          return questions;
      }
    }
    async function loadQuizzes() {
      const quizzes: StaffQuiz[] = [];
      for (let offset = 0; live; offset += 20) {
        const page = await quizRequest<StaffQuiz[]>(
          `/quizzes?limit=20&offset=${offset}`,
        );
        quizzes.push(...page);
        if (page.length < 20) break;
      }
      return quizzes;
    }
    Promise.all([loadQuestions(), loadQuizzes()])
      .then(([questions, quizzes]) => {
        if (live) setData({ questions, quizzes });
      })
      .catch((e: Error) => {
        if (live && e.name !== "AbortError") setError(e.message);
      });
    return () => {
      live = false;
      controller.abort();
    };
  }, []);
  return (
    <>
      <PageHeading
        eyebrow="TEACHING WORKSPACE"
        title="Course overview"
        description="Discrete Mathematics I · Resources, readiness and teaching tools."
      />
      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}
      {!data && !error && <p role="status">Loading course overview…</p>}
      <section className="royal-overview" aria-label="Course metrics">
        <div>
          <p>Questions in Question Bank</p>
          <strong>{data?.questions.length ?? "—"}</strong>
          <Link href="/teacher/questions">Explore collection →</Link>
        </div>
        <div>
          <p>Available quizzes</p>
          <strong>
            {data?.quizzes.filter((q) => q.status === "ACTIVE").length ?? "—"}
          </strong>
          <Link href="/teacher/quizzes">Manage quizzes →</Link>
        </div>
        <div>
          <p>Topics represented</p>
          <strong>
            {data ? new Set(data.questions.map((q) => q.topic.id)).size : "—"}
          </strong>
          <span>Primary topics with saved questions</span>
        </div>
      </section>
      <div className="section-heading">
        <h2>Requires attention</h2>
        <span className="muted small">Course readiness</span>
      </div>
      <div className="attention-grid">
        <section className="panel attention-card">
          <span className="development-label">IN DEVELOPMENT</span>
          <h3>Unreviewed answers</h3>
          <p>Manual review workflow</p>
          <p className="field-hint">
            Review counts will appear when this workflow is available.
          </p>
        </section>
        <Link className="panel attention-card" href="/teacher/quizzes">
          <span className="eyebrow">QUIZ PREPARATION</span>
          <h3>
            {data
              ? data.quizzes.filter((q) => q.status === "DRAFT").length
              : "—"}{" "}
            draft quizzes
          </h3>
          <p>Open Quiz Management to continue preparing your assessments →</p>
        </Link>
      </div>
      <section className="panel course-collection">
        <div className="panel-heading">
          <div>
            <h2>From your question bank</h2>
            <p>A selection from the course collection</p>
          </div>
          <Link className="text-link" href="/teacher/questions">
            View all →
          </Link>
        </div>
        <div className="question-preview-list">
          {data?.questions.slice(0, 3).map((q) => (
            <Link href={`/teacher/questions/${q.id}/edit`} key={q.id}>
              <span className="question-preview-id">#{q.id}</span>
              <div>
                <strong>{q.question_text}</strong>
                <p>
                  {q.topic.name} · {typeLabels[q.response_type]}
                </p>
              </div>
              <span>→</span>
            </Link>
          ))}
        </div>
        {data?.questions.length === 0 && (
          <p>No questions yet. Start your collection in Question Bank.</p>
        )}
      </section>
    </>
  );
}

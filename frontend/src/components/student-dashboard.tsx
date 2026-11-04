"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { quizzesApi, type QuizSummary } from "@/lib/quizzes";
import { learningApi, type LearningSummary } from "@/lib/learning";
import { useProgress } from "@/lib/use-progress";
import { CourseTopics } from "./course-topics";
import { PageHeading } from "./page-heading";
import {
  ProgressStatus,
  ProgressOverview,
  PerformanceRows,
  ProgressHistory,
  ProgressEmpty,
} from "./progress-panels";
export function TopicCards() {
  return <CourseTopics />;
}
export function StudentDashboard() {
  const { data, error, retry } = useProgress();
  const [quizzes, setQuizzes] = useState<QuizSummary[] | null>(null);
  const [quizError, setQuizError] = useState(false);
  const [learning, setLearning] = useState<LearningSummary | null>(null);
  const [learningError, setLearningError] = useState(false);
  useEffect(() => {
    let live = true;
    quizzesApi
      .list()
      .then((q) => {
        if (live) setQuizzes(q);
      })
      .catch(() => {
        if (live) setQuizError(true);
      });
    return () => {
      live = false;
    };
  }, []);
  useEffect(() => {
    let live = true;
    learningApi
      .summary()
      .then((summary) => {
        if (live) setLearning(summary);
      })
      .catch(() => {
        if (live) setLearningError(true);
      });
    return () => {
      live = false;
    };
  }, []);
  return (
    <>
      <PageHeading
        eyebrow="DISCRETE MATHEMATICS I"
        title="Welcome back"
        description="Your learning overview and next steps."
      />
      {!data ? (
        <ProgressStatus error={error} retry={retry} />
      ) : (
        <>
          <div className="section-heading">
            <h2>Progress overview</h2>
            <Link className="text-link" href="/student/progress">
              Your progress →
            </Link>
          </div>
          <ProgressOverview data={data} />
          {data.overview.completed_attempts === 0 && <ProgressEmpty />}
          <section className="panel topic-performance">
            <div className="panel-heading">
              <div>
                <h2>Topic performance</h2>
                <p>
                  Auto-graded practice accuracy across all completed attempts.
                  Written responses are tracked separately.
                </p>
              </div>
            </div>
            <PerformanceRows items={data.topics} />
          </section>
          <div className="section-heading">
            <h2>Recent activity</h2>
            <Link className="text-link" href="/student/quizzes">
              All quiz attempts →
            </Link>
          </div>
          <ProgressHistory attempts={data.recent_attempts} compact />
        </>
      )}
      <div className="section-heading">
        <h2>Practice and feedback</h2>
        <Link className="text-link" href="/student/practice">
          Topic practice →
        </Link>
      </div>
      {learningError ? (
        <p role="alert">
          Your practice summary could not be loaded.{" "}
          <Link href="/student/practice">Open practice to retry.</Link>
        </p>
      ) : !learning ? (
        <p role="status">Loading learning summary…</p>
      ) : (
        <section className="panel learning-summary">
          <div>
            <p className="eyebrow">CONTINUE LEARNING</p>
            <h2>{learning.continue_learning.title}</h2>
            <p>{learning.continue_learning.description}</p>
            <Link
              className="button button-primary"
              href={
                learning.continue_learning.kind === "RESUME_ATTEMPT"
                  ? `/student/quizzes/attempts/${learning.continue_learning.attempt_id}`
                  : "/student/practice"
              }
            >
              {learning.continue_learning.kind === "RESUME_ATTEMPT"
                ? "Resume"
                : "Choose topic"}
            </Link>
          </div>
          <div className="learning-metrics">
            <span>
              <strong>{learning.overview.total_attempted_questions}</strong>{" "}
              questions answered
            </span>
            <span>
              <strong>{learning.overview.completed_practice_sessions}</strong>{" "}
              completed sessions
            </span>
            <span>
              <strong>{learning.overview.pending_grading_count}</strong>{" "}
              responses awaiting grading
            </span>
          </div>
        </section>
      )}
      <div className="section-heading">
        <h2>Available quizzes</h2>
        <Link className="text-link" href="/student/quizzes">
          Browse & start →
        </Link>
      </div>
      {quizError ? (
        <p role="alert">
          Available quizzes could not be loaded.{" "}
          <Link href="/student/quizzes">Open quizzes to retry.</Link>
        </p>
      ) : !quizzes ? (
        <p role="status">Loading quizzes…</p>
      ) : (
        <div className="quiz-list">
          {quizzes.slice(0, 4).map((q) => (
            <article className="panel quiz-panel" key={q.id}>
              <h3>{q.title}</h3>
              <p>{q.description}</p>
              <p>
                {q.question_count} questions · {q.total_points} points
              </p>
              <Link className="text-link" href="/student/quizzes">
                Open quizzes →
              </Link>
            </article>
          ))}
          {quizzes.length === 0 && <p>No quizzes are available yet.</p>}
        </div>
      )}
    </>
  );
}

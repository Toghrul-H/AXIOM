"use client";
import Link from "next/link";
import { useEffect, useState, type CSSProperties } from "react";
import { useAuth } from "@/components/auth-provider";
import { quizzesApi, type QuizSummary } from "@/lib/quizzes";
import { learningApi, type LearningSummary } from "@/lib/learning";
import { personalTasksApi, type PersonalTask } from "@/lib/personal-tasks";
import { announcementsApi, type Announcement } from "@/lib/announcements";
import { useProgress } from "@/lib/use-progress";
import { PageHeading } from "./page-heading";
import {
  ProgressStatus,
  ProgressOverview,
  PerformanceRows,
  ProgressHistory,
  ProgressEmpty,
} from "./progress-panels";
import { PersonalTasks } from "./personal-tasks";
import { StudentCalendar } from "./student-calendar";
import { WeeklyActivity } from "./weekly-activity";

function displayName(email: string | undefined) {
  const local = email?.split("@", 1)[0] ?? "student";
  return local
    .replace(/[._-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function StudentDashboard() {
  const { user } = useAuth();
  const { data, error, retry } = useProgress();
  const [quizzes, setQuizzes] = useState<QuizSummary[] | null>(null);
  const [quizError, setQuizError] = useState(false);
  const [learning, setLearning] = useState<LearningSummary | null>(null);
  const [learningError, setLearningError] = useState(false);
  const [tasks, setTasks] = useState<PersonalTask[] | null>(null);
  const [taskError, setTaskError] = useState(false);
  const [taskRevision, setTaskRevision] = useState(0);
  const [announcements, setAnnouncements] = useState<Announcement[] | null>(
    null,
  );
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
  const retryTasks = () => {
    setTaskError(false);
    setTasks(null);
    setTaskRevision((revision) => revision + 1);
  };
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
  useEffect(() => {
    let live = true;
    personalTasksApi
      .list()
      .then((items) => {
        if (live) setTasks(items);
      })
      .catch(() => {
        if (live) setTaskError(true);
      });
    return () => {
      live = false;
    };
  }, [taskRevision]);
  useEffect(() => {
    let live = true;
    announcementsApi
      .list()
      .then((items) => {
        if (live) setAnnouncements(items);
      })
      .catch(() => {
        if (live) setAnnouncements([]);
      });
    return () => {
      live = false;
    };
  }, []);
  const accuracy = data?.overview.auto_graded_accuracy;
  return (
    <>
      <PageHeading
        eyebrow="DISCRETE MATHEMATICS I"
        title={`Welcome back, ${displayName(user?.email)}`}
        description="Your live learning overview, study plan, and next steps."
      />
      {!data ? (
        <ProgressStatus error={error} retry={retry} />
      ) : (
        <>
          <section className="dashboard-hero-grid">
            <div className="dashboard-summary panel">
              <div>
                <p className="eyebrow">PRACTICE ACCURACY</p>
                <h2>
                  {accuracy === null
                    ? "Start your first quiz"
                    : `${accuracy}% accurate`}
                </h2>
                <p>
                  Based only on automatically graded answers in completed
                  attempts.
                </p>
                <Link
                  className="button button-primary"
                  href="/student/practice"
                >
                  Practice by topic
                </Link>
              </div>
              <div
                className="accuracy-ring"
                aria-label={
                  accuracy === null
                    ? "No practice accuracy yet"
                    : `${accuracy}% practice accuracy`
                }
                role="img"
                style={{ "--accuracy": `${accuracy ?? 0}%` } as CSSProperties}
              >
                <span>{accuracy === null ? "—" : `${accuracy}%`}</span>
              </div>
            </div>
            <div className="quick-actions panel">
              <p className="eyebrow">QUICK ACTIONS</p>
              <Link href="/student/practice">
                Practice questions <span>→</span>
              </Link>
              <Link href="/student/quizzes">
                Browse quizzes <span>→</span>
              </Link>
              <Link href="/student/course">
                Open course <span>→</span>
              </Link>
              <Link href="/student/progress">
                Review progress <span>→</span>
              </Link>
            </div>
          </section>
          <div className="section-heading">
            <h2>Learning at a glance</h2>
            <Link className="text-link" href="/student/progress">
              Your progress →
            </Link>
          </div>
          <ProgressOverview data={data} />
          {data.overview.completed_attempts === 0 && <ProgressEmpty />}
          <div className="dashboard-two-column">
            <WeeklyActivity activity={data.weekly_activity} />
            <section className="panel topic-performance">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">TOPIC INSIGHT</p>
                  <h2>Topic performance</h2>
                </div>
              </div>
              <PerformanceRows items={data.topics} />
            </section>
          </div>
          <section className="panel announcements-preview">
            <p className="eyebrow">COURSE UPDATES</p>
            <h2>Latest announcements</h2>
            {announcements === null ? (
              <p role="status">Loading announcements…</p>
            ) : announcements.length === 0 ? (
              <p>No course announcements have been published yet.</p>
            ) : (
              announcements.slice(0, 3).map((item) => (
                <article
                  className={`announcement-preview ${item.read_at ? "" : "is-unread"}`}
                  key={item.id}
                >
                  <span>
                    {item.category === "IMPORTANT" ? "Important" : "General"}
                  </span>
                  <h3>{item.title}</h3>
                  <p>{item.body}</p>
                  {item.link && (
                    <Link
                      href={item.link}
                      onClick={() => void announcementsApi.markRead(item.id)}
                    >
                      Open update →
                    </Link>
                  )}
                </article>
              ))
            )}
          </section>
          <div className="section-heading">
            <h2>Recent activity</h2>
            <Link className="text-link" href="/student/quizzes">
              All quiz attempts →
            </Link>
          </div>
          {data.recent_attempts.length ? (
            <ProgressHistory attempts={data.recent_attempts} compact />
          ) : (
            <p className="empty-inline">
              Completed quiz activity will appear here.
            </p>
          )}
        </>
      )}
      <section className="dashboard-two-column dashboard-planning">
        <StudentCalendar tasks={tasks} />
        {taskError ? (
          <section className="panel error-state" role="alert">
            <p>Tasks could not be loaded.</p>
            <button className="button button-secondary" onClick={retryTasks}>
              Retry tasks
            </button>
          </section>
        ) : (
          <PersonalTasks tasks={tasks} onChange={setTasks} />
        )}
      </section>
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

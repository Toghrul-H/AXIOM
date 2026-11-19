"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  BellRing,
  BookOpen,
  CheckCircle2,
  ClipboardCheck,
  FileQuestion,
  GraduationCap,
  Eye,
  Megaphone,
  PenLine,
  UsersRound,
} from "lucide-react";
import { useAuth } from "./auth-provider";
import { PageHeading } from "./page-heading";
import { announcementsApi, type Announcement } from "@/lib/announcements";
import { gradingRequest, type Queue } from "@/lib/manual-grading";
import { quizRequest, type StaffQuiz } from "@/lib/quizzes";
import { recruitmentApi, type StaffVacancy } from "@/lib/recruitment";

type DashboardData = {
  announcements: Announcement[];
  grading: Queue;
  quizzes: StaffQuiz[];
  vacancies: StaffVacancy[];
};

function displayDate(value: string | null) {
  return value
    ? new Intl.DateTimeFormat("en-GB", {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      }).format(new Date(value))
    : "Date unavailable";
}

export function TeacherDashboard() {
  const { user, enterStudentView } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);

  function retry() {
    setData(null);
    setError("");
    setRevision((value) => value + 1);
  }

  useEffect(() => {
    let active = true;
    Promise.all([
      gradingRequest<Queue>("?status=pending&offset=0&limit=4"),
      quizRequest<StaffQuiz[]>("/quizzes?limit=100&offset=0"),
      recruitmentApi.staff(),
      announcementsApi.managed(),
    ])
      .then(([grading, quizzes, vacancies, announcements]) => {
        if (active) setData({ grading, quizzes, vacancies, announcements });
      })
      .catch((reason: Error) => {
        if (active)
          setError(
            reason.message || "The teaching workspace could not be loaded.",
          );
      });
    return () => {
      active = false;
    };
  }, [revision]);

  const metrics = useMemo(() => {
    const pendingApplications = data?.vacancies.reduce(
      (total, vacancy) =>
        total +
        (vacancy.status_counts.SUBMITTED ?? 0) +
        (vacancy.status_counts.UNDER_REVIEW ?? 0),
      0,
    );
    return {
      activeQuizzes: data?.quizzes.filter((quiz) => quiz.status === "ACTIVE")
        .length,
      pendingApplications,
      pendingGrading: data?.grading.total,
      publishedAnnouncements: data?.announcements.filter(
        (announcement) => announcement.status === "published",
      ).length,
    };
  }, [data]);

  const publishedAnnouncements = data?.announcements
    .filter((announcement) => announcement.status === "published")
    .slice(0, 3);
  const pendingVacancies = data?.vacancies.filter(
    (vacancy) =>
      (vacancy.status_counts.SUBMITTED ?? 0) +
        (vacancy.status_counts.UNDER_REVIEW ?? 0) >
      0,
  );
  const displayName = user?.email.split("@", 1)[0] || "Instructor";

  return (
    <main className="teacher-dashboard">
      <PageHeading
        eyebrow="TEACHING WORKSPACE"
        title={`Welcome back, ${displayName}`}
        description="A focused overview of current teaching work and the next actions available to you."
      />
      {["LECTURER", "ADMIN"].includes(user?.role ?? "") && (
        <div className="teacher-dashboard-view-action">
          <button
            className="button button-secondary"
            onClick={enterStudentView}
            type="button"
          >
            <Eye size={16} aria-hidden="true" />
            Student View
          </button>
        </div>
      )}

      {error ? (
        <section className="error-message" role="alert">
          <p>{error}</p>
          <button className="button button-secondary" onClick={retry}>
            Retry
          </button>
        </section>
      ) : !data ? (
        <p role="status">Loading your teaching workspace…</p>
      ) : (
        <>
          <section className="teacher-metrics" aria-label="Teaching overview">
            <Link
              className="teacher-metric metric-grading"
              href="/teacher/grading"
            >
              <ClipboardCheck aria-hidden="true" />
              <span>Pending grading</span>
              <strong>{metrics.pendingGrading}</strong>
              <small>Written responses awaiting review</small>
            </Link>
            <Link
              className="teacher-metric metric-quizzes"
              href="/teacher/quizzes"
            >
              <CheckCircle2 aria-hidden="true" />
              <span>Active quizzes</span>
              <strong>{metrics.activeQuizzes}</strong>
              <small>Currently available assessments</small>
            </Link>
            <Link
              className="teacher-metric metric-applications"
              href="/teacher/recruitment"
            >
              <UsersRound aria-hidden="true" />
              <span>Pending applications</span>
              <strong>{metrics.pendingApplications}</strong>
              <small>Submitted or under review</small>
            </Link>
            <Link
              className="teacher-metric metric-announcements"
              href="/teacher/announcements"
            >
              <Megaphone aria-hidden="true" />
              <span>Published announcements</span>
              <strong>{metrics.publishedAnnouncements}</strong>
              <small>Visible to students</small>
            </Link>
          </section>

          <section className="teacher-work-grid" aria-label="Operational work">
            <article className="panel teacher-priority-panel">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">PRIORITY ACTIONS</p>
                  <h2>Requires attention</h2>
                </div>
                <Link className="text-link" href="/teacher/grading">
                  Open grading →
                </Link>
              </div>
              {data.grading.items.length || pendingVacancies?.length ? (
                <div className="teacher-action-list">
                  {data.grading.items.map((attempt) => (
                    <Link
                      href={`/teacher/grading/${attempt.attempt_id}`}
                      key={attempt.attempt_id}
                    >
                      <ClipboardCheck aria-hidden="true" />
                      <span>
                        <strong>{attempt.quiz_title}</strong>
                        <small>
                          {attempt.pending_count} of{" "}
                          {attempt.manual_answer_count} response(s) awaiting
                          grading
                        </small>
                      </span>
                      <span aria-hidden="true">→</span>
                    </Link>
                  ))}
                  {pendingVacancies?.map((vacancy) => {
                    const pending =
                      (vacancy.status_counts.SUBMITTED ?? 0) +
                      (vacancy.status_counts.UNDER_REVIEW ?? 0);
                    return (
                      <Link href="/teacher/recruitment" key={vacancy.id}>
                        <UsersRound aria-hidden="true" />
                        <span>
                          <strong>{vacancy.course_name}</strong>
                          <small>
                            {pending} application(s) awaiting a decision
                          </small>
                        </span>
                        <span aria-hidden="true">→</span>
                      </Link>
                    );
                  })}
                </div>
              ) : (
                <div className="teacher-empty">
                  <CheckCircle2 aria-hidden="true" />
                  <p>
                    No submitted grading or demonstrator applications need
                    attention right now.
                  </p>
                </div>
              )}
            </article>

            <article className="panel teacher-quick-actions">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">QUICK ACTIONS</p>
                  <h2>Teaching tools</h2>
                </div>
              </div>
              <div>
                <Link href="/teacher/quizzes">
                  <PenLine aria-hidden="true" /> Manage quizzes
                </Link>
                <Link href="/teacher/questions">
                  <FileQuestion aria-hidden="true" /> Question Bank
                </Link>
                <Link href="/teacher/announcements">
                  <BellRing aria-hidden="true" /> Manage announcements
                </Link>
                <Link href="/teacher/recruitment">
                  <UsersRound aria-hidden="true" /> Review applications
                </Link>
                <Link href="/teacher/course">
                  <BookOpen aria-hidden="true" /> Manage course
                </Link>
                <Link href="/teacher/grading">
                  <GraduationCap aria-hidden="true" /> Manual grading
                </Link>
              </div>
            </article>
          </section>

          <section className="panel teacher-activity-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">RECENT ACTIVITY</p>
                <h2>Published announcements</h2>
              </div>
              <Link className="text-link" href="/teacher/announcements">
                Manage announcements →
              </Link>
            </div>
            {publishedAnnouncements?.length ? (
              <div className="teacher-activity-list">
                {publishedAnnouncements.map((announcement) => (
                  <Link href="/teacher/announcements" key={announcement.id}>
                    <Megaphone aria-hidden="true" />
                    <span>
                      <strong>{announcement.title}</strong>
                      <small>
                        {announcement.category === "IMPORTANT"
                          ? "Important"
                          : "General"}{" "}
                        · {displayDate(announcement.published_at)}
                      </small>
                    </span>
                    <span className="status-chip">Published</span>
                  </Link>
                ))}
              </div>
            ) : (
              <p className="empty-inline">
                No published announcements are available yet.
              </p>
            )}
          </section>
        </>
      )}
    </main>
  );
}

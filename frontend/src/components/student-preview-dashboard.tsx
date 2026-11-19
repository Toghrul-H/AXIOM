"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BookOpen, ClipboardList, Megaphone } from "lucide-react";

import { announcementsApi, type Announcement } from "@/lib/announcements";
import { PageHeading } from "./page-heading";

export function StudentPreviewDashboard() {
  const [announcements, setAnnouncements] = useState<Announcement[] | null>(
    null,
  );
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    announcementsApi
      .list()
      .then((items) => active && setAnnouncements(items))
      .catch(
        () => active && setError("Published announcements are unavailable."),
      );
    return () => {
      active = false;
    };
  }, []);

  return (
    <main className="student-preview-dashboard">
      <PageHeading
        eyebrow="STUDENT PREVIEW MODE"
        title="Published learning content"
        description="This neutral preview never loads student progress, tasks, attempts, grades, messages, or Study Partner data."
      />
      <section className="panel preview-notice" role="status">
        <strong>Read-only student preview</strong>
        <p>
          Only resources that are published and accessible to students appear
          here. Quiz and practice submissions are unavailable.
        </p>
      </section>
      <section
        className="student-preview-actions"
        aria-label="Published learning areas"
      >
        <Link href="/student/course" className="panel">
          <BookOpen aria-hidden="true" />
          <h2>Course and materials</h2>
          <p>Inspect published chapters, lessons, and course materials.</p>
        </Link>
        <Link href="/student/quizzes" className="panel">
          <ClipboardList aria-hidden="true" />
          <h2>Active quizzes</h2>
          <p>
            Inspect quizzes available to students without starting an attempt.
          </p>
        </Link>
      </section>
      <section
        className="panel student-preview-announcements"
        aria-labelledby="preview-announcements"
      >
        <div>
          <Megaphone aria-hidden="true" />
          <h2 id="preview-announcements">Published announcements</h2>
        </div>
        {error ? (
          <p className="field-error" role="alert">
            {error}
          </p>
        ) : announcements === null ? (
          <p role="status">Loading announcements…</p>
        ) : announcements.length ? (
          <ul>
            {announcements.map((item) => (
              <li key={item.id}>
                <strong>{item.title}</strong>
                <p>{item.body}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p>No published announcements are available.</p>
        )}
      </section>
    </main>
  );
}

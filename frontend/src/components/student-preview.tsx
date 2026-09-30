import Link from "next/link";
import { ArrowLeft, BookOpen, Shapes, ChartNoAxesCombined } from "lucide-react";
import { CourseTopics } from "./course-topics";
import { PageHeading } from "./page-heading";

export function StudentPreview({
  section,
}: {
  section: "learn" | "practice" | "progress";
}) {
  if (section === "learn")
    return (
      <>
        <PageHeading
          eyebrow="THE COURSE"
          title="See the bigger picture."
          description="An overview of the ideas at the heart of Discrete Mathematics I."
        />
        <div className="info-banner">
          <BookOpen size={18} />
          <span>
            Course outline preview. Lessons and learning materials will be added
            in a later milestone.
          </span>
        </div>
        <CourseTopics outline />
      </>
    );
  const practice = section === "practice";
  const Icon = practice ? Shapes : ChartNoAxesCombined;
  return (
    <>
      <PageHeading
        eyebrow="STUDENT WORKSPACE"
        title={
          practice
            ? "A place to put ideas into practice."
            : "See your understanding grow."
        }
        description={
          practice
            ? "Practice will help turn familiar concepts into confident understanding."
            : "Your learning journey will find a home here."
        }
      />
      <section className="panel future-panel">
        <span className="future-icon">
          <Icon size={36} />
        </span>
        <span className="demo-badge">Planned feature</span>
        <h2>
          {practice
            ? "Practice is on the horizon."
            : "Progress starts with a first step."}
        </h2>
        <p>
          {practice
            ? "Topic-based questions, feedback, and explanations are planned for a later milestone. This page previews where practice will live."
            : "Progress tracking has not been built yet. The values on the dashboard are illustrative only, and no activity is recorded."}
        </p>
        <Link href="/student" className="button button-secondary">
          <ArrowLeft size={16} />
          Back to dashboard
        </Link>
      </section>
    </>
  );
}

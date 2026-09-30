"use client";
import { useProgress } from "@/lib/use-progress";
import { PageHeading } from "./page-heading";
import {
  ProgressStatus,
  ProgressOverview,
  PerformanceRows,
  ProgressHistory,
  ProgressEmpty,
  ProgressCoverage,
} from "./progress-panels";
export function StudentProgress() {
  const { data, error, retry } = useProgress();
  return (
    <>
      <PageHeading
        eyebrow="YOUR LEARNING"
        title="Your progress"
        description="Auto-graded practice accuracy is based only on answered questions with automatic correctness results. Written responses are tracked separately."
      />
      {!data ? (
        <ProgressStatus error={error} retry={retry} />
      ) : (
        <>
          <div className="section-heading">
            <h2>Overview</h2>
            <span className="muted small">All completed attempts</span>
          </div>
          <ProgressOverview data={data} detailed />
          {data.overview.completed_attempts === 0 && <ProgressEmpty />}
          <section className="panel topic-performance">
            <div className="panel-heading">
              <h2>Performance by topic</h2>
            </div>
            <PerformanceRows
              items={data.topics}
              detailed={data.overview.completed_attempts > 0}
            />
          </section>
          <section className="panel topic-performance">
            <div className="panel-heading">
              <h2>Performance by skill</h2>
            </div>
            <PerformanceRows
              items={data.skills}
              detailed={data.overview.completed_attempts > 0}
            />
          </section>
          <ProgressCoverage data={data} />
          <div className="section-heading">
            <h2>Recent quiz activity</h2>
            <span className="muted small">Latest ten completed attempts</span>
          </div>
          {data.recent_attempts.length ? (
            <ProgressHistory attempts={data.recent_attempts} />
          ) : (
            <p className="empty-inline">Completed attempts will appear here.</p>
          )}
        </>
      )}
    </>
  );
}

import Link from "next/link";
import type { Performance, ProgressData } from "@/lib/progress";
export function ProgressStatus({
  error,
  retry,
}: {
  error: string;
  retry: () => void;
}) {
  return error ? (
    <div className="panel error-state" role="alert">
      <p>{error}</p>
      <button className="button button-secondary" onClick={retry}>
        Retry progress
      </button>
    </div>
  ) : (
    <p className="panel empty-inline" role="status">
      Loading progress…
    </p>
  );
}
export function ProgressOverview({
  data,
  detailed = false,
}: {
  data: ProgressData;
  detailed?: boolean;
}) {
  const o = data.overview;
  const metrics = [
    ["Quizzes completed", o.completed_quizzes],
    ["Questions answered", o.questions_answered],
    [
      "Auto-graded practice accuracy",
      o.auto_graded_accuracy === null
        ? "No data"
        : `${o.auto_graded_accuracy}%`,
    ],
  ];
  if (detailed) metrics.push(["Completed attempts", o.completed_attempts]);
  return (
    <div className="stat-grid overview-metrics">
      {metrics.map(([label, value]) => (
        <article className="stat-card" key={label}>
          <p>{label}</p>
          <strong>{value}</strong>
        </article>
      ))}
    </div>
  );
}
export function PerformanceRows({
  items,
  detailed = false,
}: {
  items: (Performance & { name: string })[];
  detailed?: boolean;
}) {
  return (
    <>
      {items.map((item) => (
        <div key={item.name} className="progress-detail-row">
          <div className="performance-row">
            <span>{item.name}</span>
            {item.accuracy_percent === null ? (
              <>
                <span className="empty-track" aria-hidden="true" />
                <small>No data</small>
              </>
            ) : (
              <>
                <progress
                  max={100}
                  value={item.accuracy_percent}
                  aria-label={`${item.name}: auto-graded practice accuracy`}
                />
                <strong>{item.accuracy_percent}%</strong>
              </>
            )}
          </div>
          {detailed && (
            <p className="field-hint">
              {item.answered_count} responses
              {item.auto_graded_count > 0
                ? ` · ${item.correct_count} / ${item.auto_graded_count} auto-graded correct`
                : item.answered_count > 0
                  ? " · Not automatically graded"
                  : " · Not attempted"}
            </p>
          )}
        </div>
      ))}
    </>
  );
}
export function ProgressHistory({
  attempts,
  compact = false,
}: {
  attempts: ProgressData["recent_attempts"];
  compact?: boolean;
}) {
  return (
    <div className="activity-list">
      {(compact ? attempts.slice(0, 5) : attempts).map((a) => (
        <Link
          className="activity-row"
          key={a.id}
          href={`/student/quizzes/attempts/${a.id}/review`}
        >
          <span>
            <strong>{a.quiz_title}</strong>
            <small>
              {new Date(a.submitted_at).toLocaleString("en-GB")} ·{" "}
              {a.answered_count} / {a.total_question_count} questions answered
            </small>
            <small>
              {a.accuracy_percent === null
                ? "No automatically graded answers"
                : `${a.correct_count} / ${a.auto_graded_count} auto-graded correct · ${a.accuracy_percent}% auto-graded practice accuracy`}
            </small>
            {a.answered_count > a.auto_graded_count && (
              <small>Includes responses without automatic grading.</small>
            )}
          </span>
          <span>Review attempt →</span>
        </Link>
      ))}
    </div>
  );
}
export function ProgressEmpty() {
  return (
    <section className="panel quiz-panel">
      <h2>No completed practice yet.</h2>
      <p>Complete a quiz to start building your progress history.</p>
      <Link className="button button-primary" href="/student/quizzes">
        Browse quizzes
      </Link>
    </section>
  );
}
export function ProgressCoverage({ data }: { data: ProgressData }) {
  return data.unattributed_topic.answered_count > 0 ||
    data.unattributed_skill.answered_count > 0 ? (
    <p className="quiz-notice">
      Some historical responses lack topic or skill metadata. They remain
      included in the overview: {data.unattributed_topic.answered_count}{" "}
      responses without a listed topic and{" "}
      {data.unattributed_skill.answered_count} without a listed skill.
    </p>
  ) : null;
}

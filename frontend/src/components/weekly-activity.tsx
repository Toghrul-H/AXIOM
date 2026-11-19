import { weekLabel } from "@/lib/dashboard-utils";
import type { ProgressData } from "@/lib/progress";

export function WeeklyActivity({
  activity,
}: {
  activity: ProgressData["weekly_activity"];
}) {
  const maximum = Math.max(1, ...activity.map((day) => day.completed_attempts));
  return (
    <section
      className="panel weekly-activity"
      aria-labelledby="weekly-activity-title"
    >
      <div className="panel-heading">
        <div>
          <p className="eyebrow">LAST 7 DAYS</p>
          <h2 id="weekly-activity-title">Learning activity</h2>
        </div>
      </div>
      <div
        className="activity-chart"
        role="img"
        aria-label="Completed practice attempts over the last seven days"
      >
        {activity.map((day) => (
          <div className="activity-bar" key={day.date}>
            <span
              aria-hidden="true"
              style={{ height: `${(day.completed_attempts / maximum) * 100}%` }}
            />
            <strong>{day.completed_attempts}</strong>
            <small>{weekLabel(day.date)}</small>
          </div>
        ))}
      </div>
      {activity.every((day) => day.completed_attempts === 0) && (
        <p className="empty-inline">
          No completed practice attempts in this period.
        </p>
      )}
    </section>
  );
}

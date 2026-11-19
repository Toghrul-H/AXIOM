"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";

import {
  calendarDays,
  dateKey,
  isToday,
  tasksByDate,
} from "@/lib/dashboard-utils";
import type { PersonalTask } from "@/lib/personal-tasks";

export function StudentCalendar({ tasks }: { tasks: PersonalTask[] | null }) {
  const [month, setMonth] = useState(
    () => new Date(new Date().getFullYear(), new Date().getMonth(), 1),
  );
  const items = useMemo(() => tasksByDate(tasks ?? []), [tasks]);
  const days = useMemo(() => calendarDays(month), [month]);
  const label = month.toLocaleDateString("en-GB", {
    month: "long",
    year: "numeric",
  });

  return (
    <section
      className="panel student-calendar"
      aria-labelledby="calendar-title"
    >
      <div className="panel-heading calendar-heading">
        <div>
          <p className="eyebrow">PLAN AHEAD</p>
          <h2 id="calendar-title">Smart calendar</h2>
        </div>
        <div className="calendar-controls">
          <button
            aria-label="Previous month"
            className="icon-button"
            onClick={() =>
              setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))
            }
            type="button"
          >
            <ChevronLeft size={18} />
          </button>
          <strong aria-live="polite">{label}</strong>
          <button
            aria-label="Next month"
            className="icon-button"
            onClick={() =>
              setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))
            }
            type="button"
          >
            <ChevronRight size={18} />
          </button>
        </div>
      </div>
      <p className="field-hint">
        Personal task due dates appear here. Published quiz deadlines and
        student academic dates are not currently available from the platform
        API.
      </p>
      <div className="calendar-weekdays" aria-hidden="true">
        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day) => (
          <span key={day}>{day}</span>
        ))}
      </div>
      <div className="calendar-grid">
        {days.map((day) => {
          const key = dateKey(day);
          const dayTasks = items[key] ?? [];
          const inMonth = day.getMonth() === month.getMonth();
          return (
            <div
              className={`calendar-day ${inMonth ? "" : "is-outside"} ${isToday(day) ? "is-today" : ""}`}
              key={key}
            >
              <span>{day.getDate()}</span>
              {dayTasks.slice(0, 2).map((task) => (
                <a href="#personal-tasks" key={task.id}>
                  {task.title}
                </a>
              ))}
              {dayTasks.length > 2 && (
                <small>+{dayTasks.length - 2} more</small>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

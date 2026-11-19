import type { PersonalTask } from "./personal-tasks";

const DAY = 86_400_000;

export function dateKey(value: Date) {
  return [
    value.getFullYear(),
    String(value.getMonth() + 1).padStart(2, "0"),
    String(value.getDate()).padStart(2, "0"),
  ].join("-");
}

export function calendarDays(month: Date) {
  const first = new Date(month.getFullYear(), month.getMonth(), 1);
  const leading = (first.getDay() + 6) % 7;
  const start = new Date(first);
  start.setDate(first.getDate() - leading);
  return Array.from(
    { length: 42 },
    (_, index) =>
      new Date(start.getFullYear(), start.getMonth(), start.getDate() + index),
  );
}

export function tasksByDate(tasks: PersonalTask[]) {
  return tasks.reduce<Record<string, PersonalTask[]>>((result, task) => {
    if (task.due_date) (result[task.due_date] ??= []).push(task);
    return result;
  }, {});
}

export function accuracyStroke(accuracy: number | null) {
  return accuracy === null ? 0 : Math.min(100, Math.max(0, accuracy));
}

export function weekLabel(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString("en-GB", {
    weekday: "short",
  });
}

export function isToday(value: Date) {
  return (
    Math.abs(
      new Date(dateKey(value)).getTime() -
        new Date(dateKey(new Date())).getTime(),
    ) < DAY
  );
}

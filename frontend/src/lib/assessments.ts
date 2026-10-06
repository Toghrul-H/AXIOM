import { apiFetch, type Role } from "./auth";
export const canManageAssessments = (role?: Role) =>
  role === "LECTURER" || role === "ADMIN";
export const eventLabels = {
  MIDTERM: "Midterm test",
  ENDTERM: "Endterm test",
  SHORT_QUIZ_RETAKE: "Short quiz retake",
  TEST_RETAKE: "Midterm / endterm retake",
  COURSEWORK_PUBLICATION: "Coursework publication",
  COURSEWORK_HAND_IN: "Coursework hand-in",
  COURSEWORK_RETAKE_PUBLICATION: "Coursework retake publication",
  COURSEWORK_RETAKE_HAND_IN: "Coursework retake hand-in",
} as const;
export type EventType = keyof typeof eventLabels;
export type Semester = {
  id: number;
  academic_year_start: number;
  term: "SPRING" | "FALL";
  display_label: string;
  updated_at: string;
};
export type Room = {
  id: number;
  room: string;
  groups: { identifier: string }[];
};
export type AssessmentEvent = {
  id: number;
  event_type: EventType;
  date: string | null;
  start_time: string | null;
  end_time: string | null;
  venue: string | null;
  notes: string | null;
  document_date: string | null;
  latest_arrival_time: string | null;
  rooms: Room[];
};
export type Detail = Semester & { events: AssessmentEvent[] };
export async function assessmentRequest<T>(
  path = "",
  method = "GET",
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const response = await apiFetch(`/assessment-configurations${path}`, {
    method,
    signal,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    if (response.status === 409)
      throw new Error(
        path.includes("/rooms")
          ? "That room or practice group is already assigned. Check the other rooms."
          : path.includes("/events")
            ? "This assessment is already configured, or still has room assignments."
            : "A configuration already exists for that academic year and term.",
      );
    throw new Error(
      typeof data?.detail === "string"
        ? data.detail
        : Array.isArray(data?.detail)
          ? data.detail.map((e: { msg: string }) => e.msg).join(" ")
          : "Unable to load or save assessment information. Please retry.",
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
export function roomInput(form: FormData) {
  const room = String(form.get("room") ?? "").trim();
  const groups = String(form.get("groups") ?? "")
    .split(/[\n,]/)
    .map((g) => g.trim())
    .filter(Boolean);
  if (!room || !groups.length)
    throw new Error("Enter a room and at least one practice group.");
  if (new Set(groups).size !== groups.length)
    throw new Error("Each practice group can appear only once in this room.");
  return { room, groups };
}
export function eventInput(form: FormData, event_type: EventType) {
  const value = (key: string) => String(form.get(key) ?? "").trim() || null;
  return {
    event_type,
    date: value("date"),
    start_time: value("start_time"),
    end_time: value("end_time"),
    venue: value("venue"),
    notes: value("notes"),
    document_date: value("document_date"),
    latest_arrival_time: value("latest_arrival_time"),
  };
}

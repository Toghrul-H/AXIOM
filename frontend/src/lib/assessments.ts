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
export const roomEventTypes: readonly EventType[] = [
  "MIDTERM",
  "ENDTERM",
  "SHORT_QUIZ_RETAKE",
  "TEST_RETAKE",
];
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
  writing_start_time: string | null;
  writing_end_time: string | null;
  venue: string | null;
  notes: string | null;
  document_date: string | null;
  latest_arrival_time: string | null;
  seating_plan: string | null;
  submission_deadline_date: string | null;
  submission_deadline_time: string | null;
  submission_venue: string | null;
  submission_instructions: string | null;
  group_deadlines: SubmissionDeadline[];
  rooms: Room[];
};
export const policyLabels = {
  SHORT_QUIZZES: "Short quizzes",
  MIDTERM: "Midterm",
  ENDTERM: "Endterm",
  COURSEWORK: "Coursework",
} as const;
export type PolicyCode = keyof typeof policyLabels;
export const policyTextFields = {
  topics: "Topics covered",
  assessment_mode: "Assessment mode",
  duration_description:
    "Duration description (for ranges or relative duration)",
  success_criteria: "Additional success criteria",
  permitted_equipment: "Permitted equipment and restrictions",
  retake_rules: "Retake rules",
  preparation_instructions: "Preparation / question guidance",
  conduct_instructions: "Instructions before, during and after the assessment",
} as const;
export const policyNumberFields = {
  duration_minutes: "Duration (minutes)",
  assessment_count: "Number of assessments",
  maximum_score:
    "Component maximum score (all quizzes combined for Short quizzes)",
  passing_score: "Component passing score",
} as const;
export type Policy = { code: PolicyCode } & Record<
  keyof typeof policyTextFields,
  string | null
> &
  Record<keyof typeof policyNumberFields, number | string | null>;
export const rulesTextFields = {
  course_topics: "Semester topics / problem sets",
  attendance_rules: "Attendance and exceptional absence rules",
  total_score_rules: "Total-score and course-passing rules",
  plus_points_rules: "Plus-point eligibility, tasks, scoring and deadlines",
} as const;
export type Rules = Record<keyof typeof rulesTextFields, string | null> & {
  plus_points_maximum: string | null;
  maximum_total_score: string | null;
  grade_boundaries: { grade: number; minimum_score: string }[];
};
export type SubmissionDeadline = {
  group_identifier: string;
  deadline_date: string | null;
  deadline_time: string | null;
  venue: string | null;
  instructions: string | null;
};
export type Detail = Semester & {
  events: AssessmentEvent[];
  policies: Policy[];
};
const optional = (form: FormData, key: string) =>
  String(form.get(key) ?? "").trim() || null;
export function policyInput(form: FormData) {
  return Object.fromEntries([
    ...Object.keys(policyTextFields).map((key) => [key, optional(form, key)]),
    ...Object.keys(policyNumberFields).map((key) => {
      const raw = optional(form, key);
      return [
        key,
        raw === null
          ? null
          : key === "duration_minutes" || key === "assessment_count"
            ? Number(raw)
            : raw,
      ];
    }),
  ]);
}
export function rulesInput(form: FormData) {
  const grade_boundaries = [1, 2, 3, 4, 5].flatMap((grade) => {
    const minimum_score = optional(form, `grade_${grade}`);
    return minimum_score === null ? [] : [{ grade, minimum_score }];
  });
  if (grade_boundaries.length && grade_boundaries.length !== 5)
    throw new Error("Enter all five grade thresholds or leave all empty.");
  return {
    ...Object.fromEntries(
      Object.keys(rulesTextFields).map((key) => [key, optional(form, key)]),
    ),
    plus_points_maximum: optional(form, "plus_points_maximum"),
    grade_boundaries,
  };
}
export function submissionInput(form: FormData) {
  return Array.from(form.keys())
    .filter((key) => /^deadline_group_\d+$/.test(key))
    .map((key) => {
      const suffix = key.slice("deadline_group_".length);
      return {
        group_identifier: optional(form, key) ?? "",
        deadline_date: optional(form, `deadline_date_${suffix}`),
        deadline_time: optional(form, `deadline_time_${suffix}`),
        venue: optional(form, `deadline_venue_${suffix}`),
        instructions: optional(form, `deadline_instructions_${suffix}`),
      };
    });
}
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
    seating_plan: value("seating_plan"),
    ...(event_type === "COURSEWORK_HAND_IN" ||
    event_type === "COURSEWORK_RETAKE_HAND_IN"
      ? {
          submission_deadline_date: value("submission_deadline_date"),
          submission_deadline_time: value("submission_deadline_time"),
          submission_venue: value("submission_venue"),
          submission_instructions: value("submission_instructions"),
          group_deadlines: submissionInput(form),
        }
      : {}),
    date: value("date"),
    start_time: value("start_time"),
    end_time: value("end_time"),
    writing_start_time: value("writing_start_time"),
    writing_end_time: value("writing_end_time"),
    venue: value("venue"),
    notes: value("notes"),
    document_date: value("document_date"),
    latest_arrival_time: value("latest_arrival_time"),
  };
}

export function roomRowsInput(form: FormData) {
  const groups = new Set<string>();
  const names = new Set<string>();
  return form.getAll("room_key").flatMap((raw, index) => {
    const key = String(raw),
      row = new FormData();
    const room = String(form.get(`room_${key}`) ?? "").trim();
    const identifiers = String(form.get(`groups_${key}`) ?? "").trim();
    if (!room && !identifiers) return [];
    row.set("room", room);
    row.set("groups", identifiers);
    try {
      const value = roomInput(row);
      if (names.has(value.room))
        throw new Error("This room appears more than once.");
      names.add(value.room);
      for (const group of value.groups) {
        if (groups.has(group))
          throw new Error(
            `Practice group ${group} is assigned to multiple rooms.`,
          );
        groups.add(group);
      }
      return [{ key, ...value }];
    } catch (error) {
      throw new Error(`Room row ${index + 1}: ${(error as Error).message}`);
    }
  });
}

// Existing API is per-room. Record each successful operation so a retry is safe.
export async function saveRoomRows(
  path: string,
  rows: ReturnType<typeof roomRowsInput>,
  saved: Map<string, Room>,
  changed: (rooms: Room[]) => void,
) {
  const unchanged = (key: string, room: Room) =>
    rows.some(
      (row) =>
        row.key === key &&
        row.room === room.room &&
        JSON.stringify(row.groups) ===
          JSON.stringify(room.groups.map((g) => g.identifier)),
    );
  try {
    // Release changed assignments first, allowing groups/room names to swap.
    for (const [key, room] of saved)
      if (!unchanged(key, room)) {
        await assessmentRequest(`${path}/${room.id}`, "DELETE");
        saved.delete(key);
        changed([...saved.values()]);
      }
    for (const { key, ...payload } of rows)
      if (!saved.has(key)) {
        const room = await assessmentRequest<Room>(path, "POST", payload);
        saved.set(key, room);
        changed([...saved.values()]);
      }
  } catch (error) {
    throw new Error(
      `Room assignments were not fully saved. Some changes may already be saved; your rows are retained. Retry Save. ${(error as Error).message}`,
    );
  }
}

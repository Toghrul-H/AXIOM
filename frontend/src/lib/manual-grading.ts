import { apiFetch } from "./auth";
import type { Review, ReviewItem } from "./quizzes";
export type GradedItem = ReviewItem & {
  manual_grading_status: "PENDING" | "COMPLETED" | "NOT_APPLICABLE";
  manual_points: number | null;
  manual_feedback: string | null;
  graded_at: string | null;
  graded_by_id: number | null;
};
export type GradingAttempt = Omit<Review, "items"> & {
  student: { id: number; email: string };
  items: GradedItem[];
};
export type Queue = {
  total: number;
  offset: number;
  limit: number;
  items: {
    attempt_id: string;
    student: { id: number; email: string };
    quiz_title: string;
    submitted_at: string;
    manual_answer_count: number;
    pending_count: number;
    grading_status: string;
  }[];
};
export async function gradingRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await apiFetch("/grading/attempts" + path, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail =
      typeof body?.detail === "string"
        ? body.detail
        : Array.isArray(body?.detail)
          ? body.detail
              .map((e: { msg?: string }) => e.msg ?? "Invalid value")
              .join(". ")
          : `Unable to load or save grading (${response.status}). Please retry.`;
    throw new Error(detail);
  }
  return response.json();
}

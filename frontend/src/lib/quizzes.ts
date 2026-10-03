import { apiFetch } from "./auth";
import type { QuestionType } from "./questions";
export type QuizSummary = {
  id: number;
  title: string;
  description: string | null;
  status: string;
  question_count: number;
  total_points: number;
  objective_points: number;
};
export type QuizEntry = {
  question_id: number;
  points: number;
  position?: number;
};
export type StaffQuiz = {
  id: number;
  title: string;
  description: string | null;
  status: "DRAFT" | "ACTIVE" | "INACTIVE";
  questions: QuizEntry[];
};
export type Answer = {
  selected_option_ids: number[];
  boolean_answer: boolean | null;
  free_response: string | null;
};
export type AttemptSummary = {
  id: string;
  quiz_id: number;
  quiz_title: string;
  status: "IN_PROGRESS" | "SUBMITTED";
  started_at: string;
  submitted_at: string | null;
  objective_score: number | null;
  objective_total: number;
};
export type AttemptItem = Answer & {
  topic_slug?: string | null;
  id: number;
  position: number;
  points: number;
  question_text: string;
  response_type: QuestionType;
  options: { id: number; text: string }[];
};
export type Attempt = AttemptSummary & { items: AttemptItem[] };
export type ReviewItem = AttemptItem & {
  manual_grading_status: "NOT_APPLICABLE" | "PENDING" | "COMPLETED";
  manual_points: number | null;
  manual_feedback: string | null;
  graded_at: string | null;
  answered: boolean;
  auto_gradable: boolean;
  is_correct: boolean | null;
  points_awarded: number | null;
  correct_option_ids: number[];
  correct_boolean: boolean | null;
  expected_answer: string | null;
  explanation: string | null;
};
export type Review = AttemptSummary & {
  correct_count: number;
  incorrect_count: number;
  unanswered_objective_count: number;
  ungraded_count: number;
  items: ReviewItem[];
};

export async function quizRequest<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await apiFetch(path, {
    method,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(
      typeof data?.detail === "string"
        ? data.detail
        : `Request failed (${response.status}). Check your input and try again.`,
    );
  }
  return response.json();
}
export const quizzesApi = {
  list: () => quizRequest<QuizSummary[]>("/student/quizzes?limit=100"),
  history: (offset = 0) =>
    quizRequest<AttemptSummary[]>(
      `/student/attempts?limit=20&offset=${offset}`,
    ),
  start: (id: number) =>
    quizRequest<Attempt>(`/student/quizzes/${id}/attempts`, "POST"),
  attempt: (id: string) => quizRequest<Attempt>(`/student/attempts/${id}`),
  save: (id: string, item: number, answer: Answer) =>
    quizRequest<Attempt>(
      `/student/attempts/${id}/answers/${item}`,
      "PUT",
      answer,
    ),
  submit: (id: string) =>
    quizRequest<Review>(`/student/attempts/${id}/submit`, "POST"),
  review: (id: string) => quizRequest<Review>(`/student/attempts/${id}/review`),
};

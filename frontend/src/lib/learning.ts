import { apiFetch } from "./auth";
import type { Attempt } from "./quizzes";

export type PracticeTopic = {
  id: number;
  slug: string;
  name: string;
  available_question_count: number;
  attempted_question_count: number;
  submitted_answer_count: number;
  pending_grading_count: number;
  graded_question_count: number;
  manual_points_awarded: number;
  manual_points_possible: number;
  graded_score_percent: number | null;
};

export type LearningSummary = {
  overview: {
    total_attempted_questions: number;
    completed_practice_sessions: number;
    in_progress_sessions: number;
    pending_grading_count: number;
    graded_question_count: number;
    manual_points_awarded: number;
    manual_points_possible: number;
    graded_score_percent: number | null;
  };
  topics: PracticeTopic[];
  continue_learning: {
    kind: "RESUME_ATTEMPT" | "START_PRACTICE" | "BROWSE_PRACTICE";
    title: string;
    description: string;
    attempt_id: string | null;
    topic_slug: string | null;
  };
};

async function request<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await apiFetch(path, {
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(
      typeof data?.detail === "string"
        ? data.detail
        : "Learning data could not be loaded. Please try again.",
    );
  }
  return response.json();
}

export const learningApi = {
  summary: () => request<LearningSummary>("/student/learning/summary"),
  topics: () => request<PracticeTopic[]>("/student/practice/topics"),
  start: (topicSlug: string, questionCount: number) =>
    request<Attempt>("/student/practice/sessions", "POST", {
      topic_slug: topicSlug,
      question_count: questionCount,
    }),
};

import { apiFetch } from "./auth";
export type Difficulty = "easy" | "medium" | "hard";
export type QuestionType =
  "FREE_RESPONSE" | "SINGLE_CHOICE" | "MULTIPLE_SELECT" | "TRUE_FALSE";
export type Lookup = { code: string; label: string; sort_order: number };
export type Topic = {
  id: number;
  name: string;
  slug: string;
  parent_id: number | null;
  parent: { id: number; name: string } | null;
  sort_order: number;
};
export type ProblemSet = {
  id: number;
  code: string;
  name: string;
  sort_order: number;
};
export type OptionInput = { id?: number; text: string; is_correct: boolean };
export type Metadata = {
  topics: Topic[];
  response_types: Lookup[];
  skill_types: Lookup[];
  problem_sets: ProblemSet[];
  assessment_suitabilities: Lookup[];
};
export type QuestionFilters = Partial<
  Record<
    | "topic_id"
    | "problem_set_id"
    | "difficulty"
    | "response_type"
    | "skill_type"
    | "assessment_suitability"
    | "is_active"
    | "q",
    string
  >
>;
export type QuestionInput = {
  topic_id: number;
  title: string | null;
  difficulty: Difficulty;
  response_type: QuestionType;
  skill_type: string;
  question_text: string;
  expected_answer: string | null;
  correct_boolean: boolean | null;
  explanation: string | null;
  is_active: boolean;
  options: OptionInput[];
  problem_set_ids: number[];
  assessment_suitability_codes: string[];
};
export type Question = Omit<
  QuestionInput,
  "topic_id" | "problem_set_ids" | "assessment_suitability_codes" | "options"
> & {
  id: number;
  created_at: string;
  updated_at: string;
  topic: Topic;
  problem_sets: ProblemSet[];
  assessment_suitabilities: Lookup[];
  options: (OptionInput & { id: number; position: number })[];
};
export type QuestionPage = {
  items: Question[];
  total: number;
  offset: number;
  limit: number;
};

export const typeLabels: Record<QuestionType, string> = {
  FREE_RESPONSE: "Free response",
  TRUE_FALSE: "True / false",
  SINGLE_CHOICE: "Single choice",
  MULTIPLE_SELECT: "Multiple select",
};

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await apiFetch(path, {
      ...init,
      cache: "no-store",
      headers: {
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw error;
    throw new ApiError(
      "Could not reach the API. Check that the frontend and FastAPI servers are running, then try again.",
      0,
    );
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    let message =
      response.status === 404
        ? "This question no longer exists."
        : "The request failed. Please try again.";
    if (response.status >= 500)
      message =
        "The question bank is unavailable. Check that FastAPI and PostgreSQL are running, then retry.";
    else if (typeof body?.detail === "string") message = body.detail;
    else if (Array.isArray(body?.detail)) {
      message = body.detail
        .map((item: { loc?: (string | number)[]; msg?: string }) => {
          const field = item.loc?.filter((part) => part !== "body").join(" · ");
          return `${field ? `${field}: ` : ""}${item.msg ?? "Invalid value"}`;
        })
        .join(". ");
    }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const questionsApi = {
  metadata: (signal?: AbortSignal) =>
    request<Metadata>("/question-metadata", { signal }),
  list: (
    offset = 0,
    limit = 12,
    signal?: AbortSignal,
    filters: QuestionFilters = {},
  ) => {
    const params = new URLSearchParams({
      offset: String(offset),
      limit: String(limit),
    });
    for (const [key, value] of Object.entries(filters)) {
      if (value) params.set(key, value);
    }
    return request<QuestionPage>(`/questions?${params}`, { signal });
  },
  get: (id: string, signal?: AbortSignal) =>
    request<Question>(`/questions/${encodeURIComponent(id)}`, { signal }),
  create: (body: QuestionInput) =>
    request<Question>("/questions", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  update: (id: number, body: QuestionInput) =>
    request<Question>(`/questions/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  remove: (id: number) =>
    request<void>(`/questions/${id}`, { method: "DELETE" }),
};

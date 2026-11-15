import { apiFetch } from "./auth";
import {
  downloadPdfDocument,
  downloadLatexDocument,
  fetchPdfDocument,
  fetchLatexDocument,
  type LatexDocument,
  type PdfDocument,
} from "./pdf-document";

export type ExamEntry = {
  question_id: number;
  points: number;
  position: number;
};
export type ExamDocumentSettings = {
  header: {
    institution_name: string;
    course_name: string;
    instructor_name: string | null;
    document_date: string | null;
    duration_minutes: number | null;
  };
  layout: {
    paper_size: "A4";
    margins: "compact" | "normal" | "wide";
    question_spacing: "compact" | "normal" | "spacious";
    page_numbering: boolean;
  };
  student_fields: {
    show_name: boolean;
    show_neptun_code: boolean;
    show_date: boolean;
  };
  questions: {
    show_points: boolean;
    answer_space: "none" | "small" | "medium" | "large";
    numbering_enabled: boolean;
    page_break_before_question_ids: number[];
  };
};
export const defaultExamDocumentSettings = (): ExamDocumentSettings => ({
  header: {
    institution_name: "Eötvös Loránd University",
    course_name: "Discrete Mathematics I",
    instructor_name: null,
    document_date: null,
    duration_minutes: null,
  },
  layout: {
    paper_size: "A4",
    margins: "normal",
    question_spacing: "normal",
    page_numbering: true,
  },
  student_fields: { show_name: true, show_neptun_code: true, show_date: true },
  questions: {
    show_points: true,
    answer_space: "medium",
    numbering_enabled: true,
    page_break_before_question_ids: [],
  },
});
export type Exam = {
  id: number;
  title: string;
  instructions: string | null;
  status: "draft" | "finalized";
  assessment_configuration_id: number | null;
  created_by_id: number;
  finalized_at: string | null;
  created_at: string;
  updated_at: string;
  questions: ExamEntry[];
  document_settings: ExamDocumentSettings;
  snapshot_available: boolean;
};
export type ExamWrite = {
  title: string;
  instructions: string | null;
  questions: Array<Pick<ExamEntry, "question_id" | "points">>;
  document_settings: ExamDocumentSettings;
};

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await apiFetch(`/exams${path}`, {
    ...init,
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      typeof body?.detail === "string"
        ? body.detail
        : "The Exam Builder request could not be completed. Please retry.",
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export const examsApi = {
  list: () => request<Exam[]>(""),
  create: (body: ExamWrite) =>
    request<Exam>("", { method: "POST", body: JSON.stringify(body) }),
  update: (id: number, body: ExamWrite) =>
    request<Exam>(`/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  remove: (id: number) => request<void>(`/${id}`, { method: "DELETE" }),
  finalize: (id: number) =>
    request<Exam>(`/${id}/finalize`, { method: "POST" }),
};

export function getExamPdf(
  id: number,
  kind: "exam" | "answer-key",
  signal?: AbortSignal,
): Promise<PdfDocument> {
  return fetchPdfDocument(
    `/exams/${id}/documents/${kind}/pdf`,
    `axiom-exam-${id}-${kind}.pdf`,
    signal,
  );
}

export async function downloadExamPdf(id: number, kind: "exam" | "answer-key") {
  downloadPdfDocument(await getExamPdf(id, kind));
}

export function getExamLatex(
  id: number,
  kind: "exam" | "answer-key",
  signal?: AbortSignal,
): Promise<LatexDocument> {
  return fetchLatexDocument(
    `/exams/${id}/documents/${kind}/tex`,
    `axiom-exam-${id}-${kind}.tex`,
    signal,
  );
}

export async function downloadExamLatex(
  id: number,
  kind: "exam" | "answer-key",
) {
  downloadLatexDocument(await getExamLatex(id, kind));
}

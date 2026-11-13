import { apiFetch } from "./auth";

export type PracticeSheetEntry = {
  question_id: number;
  points: number | null;
  position: number;
};

export type PracticeSheetVariant = {
  id: number;
  label: string;
  seed: string;
  generator_version: string;
  generated_at: string;
  question_count: number;
};

export type PracticeSheetDocumentSettings = {
  header: {
    institution_name: string;
    course_name: string;
    instructor_name: string | null;
    document_date: string | null;
    logo_visible: boolean;
  };
  layout: {
    paper_size: "A4";
    margins: "compact" | "normal" | "wide";
    question_spacing: "compact" | "normal" | "spacious";
  };
  questions: {
    show_points: boolean;
    answer_space: "none" | "small" | "medium" | "large";
    numbering_enabled: boolean;
    page_break_before_question_ids: number[];
  };
};

export const defaultPracticeSheetDocumentSettings =
  (): PracticeSheetDocumentSettings => ({
    header: {
      institution_name: "Eötvös Loránd University",
      course_name: "Discrete Mathematics I",
      instructor_name: null,
      document_date: null,
      logo_visible: true,
    },
    layout: {
      paper_size: "A4",
      margins: "normal",
      question_spacing: "normal",
    },
    questions: {
      show_points: true,
      answer_space: "medium",
      numbering_enabled: true,
      page_break_before_question_ids: [],
    },
  });

export type PracticeSheet = {
  id: number;
  title: string;
  instructions: string | null;
  status: "draft" | "finalized";
  created_by_id: number;
  finalized_at: string | null;
  created_at: string;
  updated_at: string;
  document_settings: PracticeSheetDocumentSettings;
  questions: PracticeSheetEntry[];
  variants: PracticeSheetVariant[];
};

export type PracticeSheetWrite = {
  title: string;
  instructions: string | null;
  questions: Array<Pick<PracticeSheetEntry, "question_id" | "points">>;
  document_settings: PracticeSheetDocumentSettings;
};

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await apiFetch(`/practice-sheets${path}`, {
    ...init,
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      typeof body?.detail === "string"
        ? body.detail
        : "The Practice Sheet request could not be completed. Please retry.",
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export const practiceSheetsApi = {
  list: () => request<PracticeSheet[]>(""),
  create: (body: PracticeSheetWrite) =>
    request<PracticeSheet>("", { method: "POST", body: JSON.stringify(body) }),
  update: (id: number, body: PracticeSheetWrite) =>
    request<PracticeSheet>(`/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  remove: (id: number) => request<void>(`/${id}`, { method: "DELETE" }),
  generateVariants: (
    id: number,
    body: { labels: string[]; seed: string; question_count?: number },
  ) =>
    request<PracticeSheetVariant[]>(`/${id}/variants`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  finalize: (id: number) =>
    request<PracticeSheet>(`/${id}/finalize`, { method: "POST" }),
};

export async function downloadPracticeSheetPdf(
  sheetId: number,
  variantId: number,
  kind: "sheet" | "answer-key",
) {
  const response = await apiFetch(
    `/practice-sheets/${sheetId}/variants/${variantId}/documents/${kind}/pdf`,
  );
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      typeof body?.detail === "string"
        ? body.detail
        : "PDF generation failed. Please retry.",
    );
  }
  if (!response.headers.get("content-type")?.startsWith("application/pdf"))
    throw new Error("The server did not return a PDF. Please retry.");
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = `axiom-practice-sheet-${sheetId}-${variantId}-${kind}.pdf`;
  try {
    document.body.appendChild(link);
    link.click();
  } finally {
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}

import { apiFetch } from "./auth";

export type ExamEntry = {
  question_id: number;
  points: number;
  position: number;
};
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
  snapshot_available: boolean;
};
export type ExamWrite = {
  title: string;
  instructions: string | null;
  questions: Array<Pick<ExamEntry, "question_id" | "points">>;
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

export async function downloadExamPdf(id: number, kind: "exam" | "answer-key") {
  const response = await apiFetch(`/exams/${id}/documents/${kind}/pdf`);
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
  link.download = `axiom-exam-${id}-${kind}.pdf`;
  try {
    document.body.appendChild(link);
    link.click();
  } finally {
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}

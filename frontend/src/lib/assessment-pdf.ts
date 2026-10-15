import { apiFetch } from "./auth";
import type { DocumentType } from "./document-preview";

export async function downloadAssessmentPdf(
  id: string,
  kind: DocumentType,
  draft: unknown,
  signal?: AbortSignal,
) {
  const response = await apiFetch(
    `/assessment-configurations/${id}/documents/${kind}/pdf`,
    {
      method: "POST",
      body: JSON.stringify(draft),
      signal,
    },
  );
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(
      typeof data?.detail === "string"
        ? data.detail
        : "PDF generation failed. Check the document fields and retry.",
    );
  }
  if (!response.headers.get("content-type")?.startsWith("application/pdf"))
    throw new Error("The server did not return a PDF. Please retry.");
  const blob = await response.blob();
  if (signal?.aborted) return;
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `axiom-${id}-${kind.toLowerCase()}.pdf`;
  try {
    document.body.appendChild(link);
    link.click();
  } finally {
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}

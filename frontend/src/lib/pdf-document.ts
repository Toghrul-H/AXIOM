import { apiFetch } from "./auth";

export type PdfDocument = {
  blob: Blob;
  filename: string;
};
export type LatexDocument = PdfDocument;

function filenameFrom(response: Response, fallback: string) {
  return (
    response.headers
      .get("content-disposition")
      ?.match(/filename="?([^";]+)"?/i)?.[1] ?? fallback
  );
}

/** Fetch an authenticated, non-persistent PDF from AXIOM's same-origin API. */
export async function fetchPdfDocument(
  path: string,
  fallbackFilename: string,
  signal?: AbortSignal,
): Promise<PdfDocument> {
  const response = await apiFetch(path, { signal, cache: "no-store" });
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
  const blob = await response.blob();
  if (blob.size === 0)
    throw new Error("The server returned an empty PDF. Please retry.");
  return { blob, filename: filenameFrom(response, fallbackFilename) };
}

/** Fetch an authenticated, non-persistent LaTeX source export. */
export async function fetchLatexDocument(
  path: string,
  fallbackFilename: string,
  signal?: AbortSignal,
): Promise<LatexDocument> {
  const response = await apiFetch(path, { signal, cache: "no-store" });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      typeof body?.detail === "string"
        ? body.detail
        : "LaTeX export failed. Please retry.",
    );
  }
  if (!response.headers.get("content-type")?.startsWith("text/x-tex"))
    throw new Error("The server did not return LaTeX source. Please retry.");
  const blob = await response.blob();
  if (blob.size === 0)
    throw new Error("The server returned empty LaTeX source. Please retry.");
  return { blob, filename: filenameFrom(response, fallbackFilename) };
}

/** Download bytes already obtained for a preview without another API request. */
export function downloadPdfDocument(pdf: PdfDocument) {
  const url = URL.createObjectURL(pdf.blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = pdf.filename;
  try {
    document.body.appendChild(link);
    link.click();
  } finally {
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}

export function downloadLatexDocument(source: LatexDocument) {
  downloadPdfDocument(source);
}

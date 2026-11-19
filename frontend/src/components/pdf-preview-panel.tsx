"use client";

import { useEffect, useRef, useState } from "react";

import { downloadPdfDocument, type PdfDocument } from "@/lib/pdf-document";

type Props = {
  title: string;
  disabled?: boolean;
  disabledMessage: string;
  loadPdf: (signal: AbortSignal) => Promise<PdfDocument>;
  onFullscreen: () => void;
};

/** Inline authoritative PDF viewer. It retains PDF bytes only in memory. */
export function PdfPreviewPanel({
  title,
  disabled = false,
  disabledMessage,
  loadPdf,
  onFullscreen,
}: Props) {
  const abort = useRef<AbortController | null>(null);
  const objectUrl = useRef<string | null>(null);
  const requestVersion = useRef(0);
  const [document, setDocument] = useState<PdfDocument | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function releaseUrl() {
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    objectUrl.current = null;
    setUrl(null);
  }

  function cancelRequest() {
    requestVersion.current += 1;
    abort.current?.abort();
    abort.current = null;
    setLoading(false);
  }

  async function preview() {
    if (disabled || loading) return;
    cancelRequest();
    releaseUrl();
    setDocument(null);
    setError("");
    const controller = new AbortController();
    const version = ++requestVersion.current;
    abort.current = controller;
    setLoading(true);
    try {
      const next = await loadPdf(controller.signal);
      if (controller.signal.aborted || version !== requestVersion.current)
        return;
      const nextUrl = URL.createObjectURL(next.blob);
      objectUrl.current = nextUrl;
      setDocument(next);
      setUrl(nextUrl);
    } catch (reason) {
      if (!controller.signal.aborted && version === requestVersion.current) {
        setError(
          reason instanceof Error
            ? reason.message
            : "Could not prepare this PDF preview. Please retry.",
        );
      }
    } finally {
      if (version === requestVersion.current) setLoading(false);
    }
  }

  useEffect(
    () => () => {
      cancelRequest();
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    },
    [],
  );

  return (
    <section className="pdf-workspace-preview" aria-label={`${title} preview`}>
      <div className="pdf-workspace-preview-toolbar">
        <div>
          <p className="eyebrow">AUTHORITATIVE PDF</p>
          <h2>{title}</h2>
        </div>
        <button
          className="button button-primary"
          type="button"
          onClick={() => void preview()}
          disabled={disabled || loading}
        >
          {loading ? "Generating…" : url ? "Refresh PDF" : "Preview PDF"}
        </button>
      </div>
      <div className="pdf-workspace-preview-body" aria-busy={loading}>
        {disabled && <p className="field-hint">{disabledMessage}</p>}
        {!disabled && !loading && !error && !url && (
          <p className="empty-inline">
            Generate the saved document to inspect the exact PDF students or
            staff will download.
          </p>
        )}
        {loading && <p role="status">Generating PDF preview…</p>}
        {error && (
          <div role="alert" className="error-message">
            <p>{error}</p>
            <button
              className="button button-secondary"
              type="button"
              onClick={() => void preview()}
            >
              Retry
            </button>
          </div>
        )}
        {url && (
          <iframe
            className="pdf-workspace-preview-frame"
            src={url}
            title={title}
          />
        )}
      </div>
      <div className="pdf-workspace-preview-actions">
        <button
          className="button button-secondary"
          type="button"
          onClick={onFullscreen}
          disabled={disabled || loading}
        >
          Open larger preview
        </button>
        <button
          className="button button-secondary"
          type="button"
          disabled={!document || loading}
          onClick={() => document && downloadPdfDocument(document)}
        >
          Download PDF
        </button>
      </div>
    </section>
  );
}

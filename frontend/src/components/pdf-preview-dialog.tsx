"use client";

import { useEffect, useRef, useState } from "react";

import { downloadPdfDocument, type PdfDocument } from "@/lib/pdf-document";

type Props = {
  open: boolean;
  title: string;
  documentKey: string;
  loadPdf: (signal: AbortSignal) => Promise<PdfDocument>;
  onClose: () => void;
};

/** A staff-only viewer for a PDF already authorized by its normal API endpoint. */
export function PdfPreviewDialog({
  open,
  title,
  documentKey,
  loadPdf,
  onClose,
}: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const restoreFocus = useRef<HTMLElement | null>(null);
  const abort = useRef<AbortController | null>(null);
  const objectUrl = useRef<string | null>(null);
  const requestVersion = useRef(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [document, setDocument] = useState<PdfDocument | null>(null);
  const [url, setUrl] = useState<string | null>(null);

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

  function close() {
    cancelRequest();
    releaseUrl();
    setDocument(null);
    setError("");
    dialog.current?.close();
    window.setTimeout(() => restoreFocus.current?.focus(), 0);
    onClose();
  }

  async function load() {
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
      if (!controller.signal.aborted && version === requestVersion.current)
        setError(
          reason instanceof Error
            ? reason.message
            : "Could not prepare this PDF preview. Please retry.",
        );
    } finally {
      if (version === requestVersion.current) setLoading(false);
    }
  }
  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    let timer: number | undefined;
    if (open) {
      restoreFocus.current = window.document
        .activeElement as HTMLElement | null;
      if (!element.open) element.showModal();
      timer = window.setTimeout(() => void load(), 0);
    } else if (element.open) {
      element.close();
      restoreFocus.current?.focus();
    }
    return () => {
      if (timer !== undefined) window.clearTimeout(timer);
    };
    // documentKey intentionally determines when a selected PDF changes. `loadPdf`
    // is an inline parent callback and must not re-fetch after unrelated rerenders.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, documentKey]);

  useEffect(
    () => () => {
      cancelRequest();
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    },
    [],
  );

  return (
    <dialog
      ref={dialog}
      className="pdf-preview-dialog"
      aria-labelledby="pdf-preview-title"
      onCancel={(event) => {
        event.preventDefault();
        close();
      }}
      onClose={() => restoreFocus.current?.focus()}
    >
      <header className="pdf-preview-header">
        <div>
          <p className="eyebrow">AUTHORITATIVE PDF</p>
          <h2 id="pdf-preview-title">{title}</h2>
        </div>
        <button
          className="button button-secondary"
          type="button"
          onClick={close}
        >
          Close
        </button>
      </header>
      <div className="pdf-preview-body" aria-busy={loading}>
        {loading && <p role="status">Generating PDF preview…</p>}
        {error && (
          <div role="alert" className="error-message">
            <p>{error}</p>
            <button
              className="button button-secondary"
              type="button"
              onClick={() => void load()}
            >
              Retry
            </button>
          </div>
        )}
        {url && (
          <>
            <iframe className="pdf-preview-frame" src={url} title={title} />
            <p className="field-hint">
              If your browser cannot display this PDF, use Download PDF below.
            </p>
          </>
        )}
      </div>
      <footer className="pdf-preview-actions">
        <button
          className="button button-secondary"
          type="button"
          onClick={close}
        >
          Close
        </button>
        <button
          className="button button-primary"
          type="button"
          disabled={!document || loading}
          onClick={() => document && downloadPdfDocument(document)}
        >
          Download PDF
        </button>
      </footer>
    </dialog>
  );
}

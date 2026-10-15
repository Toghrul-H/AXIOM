"use client";
import { useEffect, useRef, useState } from "react";
import { downloadAssessmentPdf } from "@/lib/assessment-pdf";
import { assessmentRequest } from "@/lib/assessments";
import {
  documentLabels,
  hasUnsavedDocumentChanges,
  snapshotEditor,
  previewScheduler,
  type DocumentType,
  type Preview,
  type PreviewNode,
} from "@/lib/document-preview";

export function PreviewNodes({ nodes }: { nodes: PreviewNode[] }) {
  return nodes.map((node, index) => {
    const content = <PreviewNodes nodes={node.children ?? []} />;
    switch (node.kind) {
      case "text":
        return <span key={index}>{node.text}</span>;
      case "strong":
        return <strong key={index}>{content}</strong>;
      case "emphasis":
        return <em key={index}>{content}</em>;
      case "underline":
        return <u key={index}>{content}</u>;
      case "heading":
        return node.level === 2 ? (
          <h2 key={index}>{content}</h2>
        ) : (
          <h3 key={index}>{content}</h3>
        );
      case "group":
        return (
          <div className="draft-paragraph" key={index}>
            {content}
          </div>
        );
      case "center":
        return (
          <div className="draft-center" key={index}>
            {content}
          </div>
        );
      case "break":
        return <br key={index} />;
      case "pagebreak":
        return <hr className="draft-pagebreak" key={index} />;
      case "rule":
        return <hr key={index} />;
      case "list":
        return node.ordered ? (
          <ol key={index}>{content}</ol>
        ) : (
          <ul key={index}>{content}</ul>
        );
      case "item":
        return <li key={index}>{content}</li>;
      case "table":
        return (
          <div className="draft-table" key={index}>
            <table>
              <tbody>{content}</tbody>
            </table>
          </div>
        );
      case "row":
        return <tr key={index}>{content}</tr>;
      case "cell":
        return <td key={index}>{content}</td>;
      default:
        return null;
    }
  });
}

export function DocumentWorkspace({
  id,
  children,
}: {
  id: string;
  children: (kind: DocumentType) => React.ReactNode;
}) {
  const editor = useRef<HTMLDivElement>(null);
  const [kind, setKind] = useState<DocumentType>("DATES_OF_ASSESSMENTS");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  const [dirty, setDirty] = useState(false),
    [retry, setRetry] = useState(0);
  const [generating, setGenerating] = useState(false),
    [pdfError, setPdfError] = useState("");
  const downloadLock = useRef(false);
  const downloadAbort = useRef<AbortController | null>(null);
  useEffect(() => () => downloadAbort.current?.abort(), []);
  async function download() {
    if (downloadLock.current || !editor.current) return;
    if (hasUnsavedDocumentChanges(editor.current, kind)) {
      setPdfError(
        "You have unsaved changes. Please save your changes before downloading the PDF.",
      );
      return;
    }
    downloadLock.current = true;
    setGenerating(true);
    setPdfError("");
    const abort = new AbortController();
    downloadAbort.current = abort;
    try {
      await downloadAssessmentPdf(
        id,
        kind,
        snapshotEditor(editor.current),
        abort.signal,
      );
    } catch (error) {
      if (!abort.signal.aborted)
        setPdfError(
          error instanceof Error
            ? error.message
            : "PDF download failed. Please retry.",
        );
    } finally {
      downloadLock.current = false;
      if (!abort.signal.aborted) setGenerating(false);
    }
  }
  useEffect(() => {
    const element = editor.current;
    if (!element) return;
    const scheduler = previewScheduler(
      () => snapshotEditor(element),
      (draft, signal) =>
        assessmentRequest<Preview>(
          `/${id}/documents/${kind}/preview`,
          "POST",
          draft,
          signal,
        ),
      (state) => {
        setLoading(state.loading);
        setError(state.error);
        if (state.preview) setPreview(state.preview);
      },
    );
    // Native events reach this element before React's delegated onChange.
    // Wait until React commits the controlled value before updating preview state.
    // Otherwise a parent render can restore the old value during the same keystroke.
    let refreshTimer: ReturnType<typeof setTimeout> | undefined;
    const refresh = () => {
      clearTimeout(refreshTimer);
      refreshTimer = setTimeout(() => {
        setDirty(Boolean(element.querySelector('form[data-dirty="true"]')));
        scheduler.schedule();
      }, 0);
    };
    element.addEventListener("input", refresh);
    element.addEventListener("change", refresh);
    // Covers add/remove deadline rows, successful saves/deletions, and loaded rules.
    const observer = new MutationObserver(refresh);
    observer.observe(element, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ["data-dirty", "disabled"],
    });
    refresh();
    return () => {
      clearTimeout(refreshTimer);
      scheduler.dispose();
      observer.disconnect();
      element.removeEventListener("input", refresh);
      element.removeEventListener("change", refresh);
    };
  }, [id, kind, retry]);
  return (
    <>
      <nav className="document-navigation" aria-label="Assessment documents">
        {Object.entries(documentLabels).map(([value, label]) => (
          <button
            key={value}
            type="button"
            aria-pressed={kind === value}
            onClick={() => {
              setPreview(null);
              setKind(value as DocumentType);
            }}
          >
            {label}
          </button>
        ))}
      </nav>
      <div className="document-workspace">
        <div
          ref={editor}
          className="document-editor-pane"
          aria-label="Assessment configuration"
        >
          {children(kind)}
        </div>
        <aside
          className="document-preview-pane"
          aria-label="Live document preview"
        >
          <header className="document-preview-toolbar">
            <h2>Draft Preview</h2>
            <button
              type="button"
              className="button button-primary"
              disabled={generating}
              onClick={download}
            >
              {generating ? "Generating PDF…" : "Download PDF"}
            </button>
            {generating && (
              <p role="status">
                Generating the selected document from your current edits…
              </p>
            )}
            {pdfError && <p role="alert">{pdfError}</p>}
            <h3>{documentLabels[kind]}</h3>
            <p className="draft-save-state" role="status">
              {dirty ? "Unsaved changes — preview only" : "Saved configuration"}
            </p>
            <div role="status" aria-live="polite">
              {loading
                ? preview
                  ? "Updating — showing previous draft"
                  : "Updating preview..."
                : !error
                  ? "Preview up to date"
                  : "Error — preview not up to date"}
            </div>
            {error && (
              <p role="alert">
                {error}{" "}
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={() => setRetry((n) => n + 1)}
                >
                  Retry
                </button>
              </p>
            )}
          </header>
          <div
            className="document-preview-scroll"
            tabIndex={0}
            aria-label="Scrollable draft document"
            aria-busy={loading}
          >
            <article className="draft-paper">
              <PreviewNodes nodes={preview?.blocks ?? []} />
              {!preview && (
                <p>
                  {loading
                    ? "Preparing document..."
                    : "Complete or correct the fields to preview this document."}
                </p>
              )}
            </article>
          </div>
        </aside>
      </div>
    </>
  );
}

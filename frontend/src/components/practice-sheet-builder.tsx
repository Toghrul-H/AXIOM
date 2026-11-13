"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ChevronDown,
  GripVertical,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react";

import {
  downloadPracticeSheetPdf,
  defaultPracticeSheetDocumentSettings,
  practiceSheetsApi,
  type PracticeSheet,
  type PracticeSheetDocumentSettings,
  type PracticeSheetEntry,
} from "@/lib/practice-sheets";
import {
  questionsApi,
  type Question,
  type QuestionFilters as Filters,
} from "@/lib/questions";
import { orderedTopics, useMetadata } from "@/lib/use-metadata";
import { useAuth } from "./auth-provider";
import { PageHeading } from "./page-heading";
import { QuestionFilters } from "./question-filters";
import { MathText } from "./math-text";

const PAGE_SIZE = 20;
const emptyDraft = () => ({
  id: null as number | null,
  title: "",
  instructions: "",
  status: "draft" as PracticeSheet["status"],
  entries: [] as PracticeSheetEntry[],
  variants: [] as PracticeSheet["variants"],
  documentSettings: defaultPracticeSheetDocumentSettings(),
});
type Draft = ReturnType<typeof emptyDraft>;
const signature = (draft: Draft) =>
  JSON.stringify({
    title: draft.title,
    instructions: draft.instructions,
    document_settings: draft.documentSettings,
    entries: draft.entries.map(({ question_id, points }) => ({
      question_id,
      points,
    })),
  });

function labelFor(index: number) {
  let value = index + 1;
  let label = "";
  while (value > 0) {
    value -= 1;
    label = String.fromCharCode(65 + (value % 26)) + label;
    value = Math.floor(value / 26);
  }
  return label;
}

export function PracticeSheetBuilder() {
  const { user } = useAuth();
  const [sheets, setSheets] = useState<PracticeSheet[]>([]);
  const [draft, setDraft] = useState(emptyDraft);
  const [savedSignature, setSavedSignature] = useState("");
  const [questions, setQuestions] = useState<Question[]>([]);
  const [previewQuestions, setPreviewQuestions] = useState<
    Record<number, Question>
  >({});
  const [filters, setFilters] = useState<Filters>({});
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingQuestions, setLoadingQuestions] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [confirmingFinalization, setConfirmingFinalization] = useState(false);
  const [variantCount, setVariantCount] = useState(2);
  const [questionsPerVariant, setQuestionsPerVariant] = useState("");
  const [variantSeed, setVariantSeed] = useState("");
  const [downloading, setDownloading] = useState<string | null>(null);
  const [draggedQuestionId, setDraggedQuestionId] = useState<number | null>(
    null,
  );
  const { metadata, error: metadataError } = useMetadata();
  const readOnly = draft.status === "finalized";
  const dirty =
    draft.id !== null && !readOnly && signature(draft) !== savedSignature;

  const fetchSheets = () => {
    void practiceSheetsApi
      .list()
      .then((items) => {
        setSheets(items);
        setLoading(false);
      })
      .catch((reason: Error) => {
        setError(reason.message);
        setLoading(false);
      });
  };
  useEffect(() => {
    fetchSheets();
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    questionsApi
      .list(offset, PAGE_SIZE, controller.signal, filters)
      .then((page) => {
        setQuestions(page.items);
        setTotal(page.total);
        setLoadingQuestions(false);
      })
      .catch((reason: Error) => {
        if (!controller.signal.aborted) {
          setError(reason.message);
          setLoadingQuestions(false);
        }
      });
    return () => controller.abort();
  }, [filters, offset]);

  useEffect(() => {
    const missing = draft.entries
      .map((entry) => entry.question_id)
      .filter((id) => !previewQuestions[id]);
    if (missing.length === 0) return;
    const controller = new AbortController();
    void Promise.all(
      missing.map((id) => questionsApi.get(String(id), controller.signal)),
    )
      .then((items) => {
        if (!controller.signal.aborted)
          setPreviewQuestions((current) => ({
            ...current,
            ...Object.fromEntries(items.map((item) => [item.id, item])),
          }));
      })
      .catch((reason: Error) => {
        if (!controller.signal.aborted) setError(reason.message);
      });
    return () => controller.abort();
  }, [draft.entries, previewQuestions]);

  const questionById = useMemo(
    () =>
      new Map([
        ...Object.values(previewQuestions).map(
          (question) => [question.id, question] as const,
        ),
        ...questions.map((question) => [question.id, question] as const),
      ]),
    [previewQuestions, questions],
  );
  const topicMap = new Map(
    questions.map((question) => [question.topic.id, question.topic]),
  );
  const groups = orderedTopics([...topicMap.values()])
    .map(({ topic, label }) => ({
      label,
      items: questions.filter((question) => question.topic.id === topic.id),
    }))
    .filter((group) => group.items.length);
  if (!user || !["LECTURER", "ADMIN"].includes(user.role)) return null;

  function open(sheet: PracticeSheet) {
    const next: Draft = {
      id: sheet.id,
      title: sheet.title,
      instructions: sheet.instructions ?? "",
      status: sheet.status,
      entries: sheet.questions,
      variants: sheet.variants,
      documentSettings: sheet.document_settings,
    };
    setDraft(next);
    setSavedSignature(signature(next));
    setConfirmingFinalization(false);
    setNotice("");
    setError("");
  }
  function replaceEntries(entries: PracticeSheetEntry[]) {
    setDraft((current) => ({
      ...current,
      entries: entries.map((entry, position) => ({ ...entry, position })),
      documentSettings: {
        ...current.documentSettings,
        questions: {
          ...current.documentSettings.questions,
          page_break_before_question_ids:
            current.documentSettings.questions.page_break_before_question_ids.filter(
              (id) => entries.some((entry) => entry.question_id === id),
            ),
        },
      },
    }));
  }
  function updateDocumentSettings(
    update: (
      settings: PracticeSheetDocumentSettings,
    ) => PracticeSheetDocumentSettings,
  ) {
    setDraft((current) => ({
      ...current,
      documentSettings: update(current.documentSettings),
    }));
  }
  function add(question: Question) {
    if (
      readOnly ||
      !question.is_active ||
      draft.entries.some((entry) => entry.question_id === question.id)
    )
      return;
    setPreviewQuestions((current) => ({ ...current, [question.id]: question }));
    replaceEntries([
      ...draft.entries,
      {
        question_id: question.id,
        points: null,
        position: draft.entries.length,
      },
    ]);
  }
  function move(index: number, delta: number) {
    const next = [...draft.entries];
    [next[index], next[index + delta]] = [next[index + delta], next[index]];
    replaceEntries(next);
  }
  function dropQuestion(targetId: number) {
    if (draggedQuestionId === null || draggedQuestionId === targetId) return;
    const from = draft.entries.findIndex(
      (entry) => entry.question_id === draggedQuestionId,
    );
    const to = draft.entries.findIndex(
      (entry) => entry.question_id === targetId,
    );
    if (from < 0 || to < 0) return;
    const next = [...draft.entries];
    const [moved] = next.splice(from, 1);
    next.splice(to, 0, moved);
    replaceEntries(next);
  }
  async function save() {
    if (busy || readOnly) return;
    if (!draft.title.trim())
      return setError("Enter a practice sheet title before saving.");
    if (
      draft.entries.some(
        (entry) =>
          entry.points !== null &&
          (!Number.isInteger(entry.points) ||
            entry.points < 1 ||
            entry.points > 1000),
      )
    )
      return setError("Points must be blank or a whole number from 1 to 1000.");
    setBusy(true);
    setError("");
    try {
      const body = {
        title: draft.title.trim(),
        instructions: draft.instructions.trim() || null,
        questions: draft.entries.map(({ question_id, points }) => ({
          question_id,
          points,
        })),
        document_settings: draft.documentSettings,
      };
      const saved =
        draft.id === null
          ? await practiceSheetsApi.create(body)
          : await practiceSheetsApi.update(draft.id, body);
      open(saved);
      setSheets((items) => [
        saved,
        ...items.filter((item) => item.id !== saved.id),
      ]);
      setNotice("Draft saved.");
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not save this practice sheet.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function remove(sheet: PracticeSheet) {
    if (
      sheet.status !== "draft" ||
      busy ||
      !window.confirm(`Delete draft “${sheet.title}”?`)
    )
      return;
    setBusy(true);
    setError("");
    try {
      await practiceSheetsApi.remove(sheet.id);
      setSheets((items) => items.filter((item) => item.id !== sheet.id));
      if (draft.id === sheet.id) {
        setDraft(emptyDraft());
        setSavedSignature("");
      }
      setNotice("Draft deleted.");
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not delete this draft.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function generateVariants() {
    if (draft.id === null || busy || dirty) return;
    if (
      !Number.isInteger(variantCount) ||
      variantCount < 1 ||
      variantCount > 26
    )
      return setError("Choose between 1 and 26 variants.");
    const perVariant =
      questionsPerVariant === "" ? undefined : Number(questionsPerVariant);
    if (
      perVariant !== undefined &&
      (!Number.isInteger(perVariant) ||
        perVariant < 1 ||
        perVariant > draft.entries.length)
    )
      return setError(
        "Questions per variant must be between 1 and the selected question count.",
      );
    const used = new Set(draft.variants.map((variant) => variant.label));
    const labels: string[] = [];
    for (let index = 0; labels.length < variantCount; index += 1) {
      const label = labelFor(index);
      if (!used.has(label)) labels.push(label);
    }
    setBusy(true);
    setError("");
    try {
      const generated = await practiceSheetsApi.generateVariants(draft.id, {
        labels,
        seed: variantSeed.trim() || crypto.randomUUID(),
        ...(perVariant === undefined ? {} : { question_count: perVariant }),
      });
      const variants = [...draft.variants, ...generated];
      setDraft((current) => ({ ...current, variants }));
      setSheets((items) =>
        items.map((item) =>
          item.id === draft.id ? { ...item, variants } : item,
        ),
      );
      setNotice(
        `Generated variant${generated.length === 1 ? "" : "s"} ${generated.map((item) => item.label).join(", ")}.`,
      );
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not generate variants.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function finalize() {
    if (draft.id === null || busy) return;
    setBusy(true);
    setError("");
    try {
      const finalized = await practiceSheetsApi.finalize(draft.id);
      open(finalized);
      setSheets((items) =>
        items.map((item) => (item.id === finalized.id ? finalized : item)),
      );
      setNotice(
        "Practice sheet finalized. Its generated variants are now fixed.",
      );
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not finalize this practice sheet.",
      );
    } finally {
      setBusy(false);
      setConfirmingFinalization(false);
    }
  }
  async function download(variantId: number, kind: "sheet" | "answer-key") {
    if (draft.id === null || downloading) return;
    if (dirty) {
      setError(
        "You have unsaved changes. Please save before downloading a PDF.",
      );
      return;
    }
    const key = `${variantId}:${kind}`;
    setDownloading(key);
    setError("");
    try {
      await downloadPracticeSheetPdf(draft.id, variantId, kind);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not download this PDF.",
      );
    } finally {
      setDownloading(null);
    }
  }

  return (
    <>
      <PageHeading
        eyebrow="TEACHING RESOURCES"
        title="Practice Sheet Builder"
        description="Build controlled practice sheets and reproducible question-set variants."
        action={
          <button
            className="button button-primary"
            onClick={() => {
              setDraft(emptyDraft());
              setSavedSignature("");
            }}
          >
            <Plus size={17} />
            New practice sheet
          </button>
        }
      />
      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="success-message" role="status">
          {notice}
        </p>
      )}
      <section className="panel exam-list" aria-label="Saved practice sheets">
        <div className="panel-heading">
          <div>
            <h2>Saved practice sheets</h2>
            <p>Drafts stay editable; finalized variants stay fixed.</p>
          </div>
          <button
            className="button button-quiet"
            onClick={() => {
              setLoading(true);
              setError("");
              fetchSheets();
            }}
            disabled={loading}
          >
            <RefreshCw size={16} className={loading ? "spin" : ""} />
            Refresh
          </button>
        </div>
        {loading ? (
          <p role="status">Loading practice sheets…</p>
        ) : sheets.length === 0 ? (
          <p>No practice sheets yet. Start a draft to create the first one.</p>
        ) : (
          <div className="exam-list-items">
            {sheets.map((sheet) => (
              <article
                key={sheet.id}
                className={
                  draft.id === sheet.id ? "exam-row selected" : "exam-row"
                }
              >
                <button
                  type="button"
                  className="exam-open"
                  onClick={() => open(sheet)}
                >
                  <strong>{sheet.title}</strong>
                  <span className={`exam-status ${sheet.status}`}>
                    {sheet.status}
                  </span>
                  <span>
                    {sheet.questions.length} question
                    {sheet.questions.length === 1 ? "" : "s"} ·{" "}
                    {sheet.variants.length} variant
                    {sheet.variants.length === 1 ? "" : "s"}
                  </span>
                </button>
                {sheet.status === "draft" && (
                  <button
                    type="button"
                    className="icon-button"
                    aria-label={`Delete ${sheet.title}`}
                    onClick={() => void remove(sheet)}
                    disabled={busy}
                  >
                    <Trash2 size={16} />
                  </button>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
      <section className="practice-sheet-workspace">
        <div className="practice-sheet-editor-pane">
          <section className="exam-builder-grid practice-sheet-editor-grid">
            <form
              className="panel quiz-panel exam-editor"
              onSubmit={(event) => {
                event.preventDefault();
                void save();
              }}
            >
              <div className="panel-heading">
                <div>
                  <h2>
                    {draft.id === null
                      ? "New practice sheet"
                      : readOnly
                        ? "Finalized practice sheet"
                        : "Edit draft"}
                  </h2>
                  <p>
                    {readOnly
                      ? "This saved sheet and its variants are read-only."
                      : "Set the question pool and variant settings."}
                  </p>
                </div>
                {draft.id !== null && (
                  <span className={`exam-status ${draft.status}`}>
                    {draft.status}
                  </span>
                )}
              </div>
              <fieldset disabled={busy || readOnly}>
                <label className="field">
                  Practice sheet title
                  <input
                    required
                    maxLength={200}
                    value={draft.title}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        title: event.target.value,
                      }))
                    }
                  />
                </label>
                <label className="field">
                  Instructions
                  <textarea
                    maxLength={20000}
                    value={draft.instructions}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        instructions: event.target.value,
                      }))
                    }
                  />
                </label>
                <details className="panel practice-document-settings" open>
                  <summary>Document Settings</summary>
                  <div className="filters-grid">
                    <label className="field">
                      Institution name
                      <input
                        required
                        maxLength={200}
                        value={draft.documentSettings.header.institution_name}
                        onChange={(event) =>
                          updateDocumentSettings((settings) => ({
                            ...settings,
                            header: {
                              ...settings.header,
                              institution_name: event.target.value,
                            },
                          }))
                        }
                      />
                    </label>
                    <label className="field">
                      Course name
                      <input
                        required
                        maxLength={200}
                        value={draft.documentSettings.header.course_name}
                        onChange={(event) =>
                          updateDocumentSettings((settings) => ({
                            ...settings,
                            header: {
                              ...settings.header,
                              course_name: event.target.value,
                            },
                          }))
                        }
                      />
                    </label>
                    <label className="field">
                      Instructor name (optional)
                      <input
                        maxLength={200}
                        value={
                          draft.documentSettings.header.instructor_name ?? ""
                        }
                        onChange={(event) =>
                          updateDocumentSettings((settings) => ({
                            ...settings,
                            header: {
                              ...settings.header,
                              instructor_name: event.target.value || null,
                            },
                          }))
                        }
                      />
                    </label>
                    <label className="field">
                      Document date (optional)
                      <input
                        type="date"
                        value={
                          draft.documentSettings.header.document_date ?? ""
                        }
                        onChange={(event) =>
                          updateDocumentSettings((settings) => ({
                            ...settings,
                            header: {
                              ...settings.header,
                              document_date: event.target.value || null,
                            },
                          }))
                        }
                      />
                    </label>
                    <label className="field">
                      Paper size
                      <select value="A4" disabled aria-label="Paper size">
                        <option value="A4">A4</option>
                      </select>
                    </label>
                    <label className="field">
                      Margins
                      <select
                        value={draft.documentSettings.layout.margins}
                        onChange={(event) =>
                          updateDocumentSettings((settings) => ({
                            ...settings,
                            layout: {
                              ...settings.layout,
                              margins: event.target
                                .value as PracticeSheetDocumentSettings["layout"]["margins"],
                            },
                          }))
                        }
                      >
                        <option value="compact">Compact</option>
                        <option value="normal">Normal</option>
                        <option value="wide">Wide</option>
                      </select>
                    </label>
                    <label className="field">
                      Question spacing
                      <select
                        value={draft.documentSettings.layout.question_spacing}
                        onChange={(event) =>
                          updateDocumentSettings((settings) => ({
                            ...settings,
                            layout: {
                              ...settings.layout,
                              question_spacing: event.target
                                .value as PracticeSheetDocumentSettings["layout"]["question_spacing"],
                            },
                          }))
                        }
                      >
                        <option value="compact">Compact</option>
                        <option value="normal">Normal</option>
                        <option value="spacious">Spacious</option>
                      </select>
                    </label>
                    <label className="field">
                      Answer space
                      <select
                        value={draft.documentSettings.questions.answer_space}
                        onChange={(event) =>
                          updateDocumentSettings((settings) => ({
                            ...settings,
                            questions: {
                              ...settings.questions,
                              answer_space: event.target
                                .value as PracticeSheetDocumentSettings["questions"]["answer_space"],
                            },
                          }))
                        }
                      >
                        <option value="none">None</option>
                        <option value="small">Small</option>
                        <option value="medium">Medium</option>
                        <option value="large">Large</option>
                      </select>
                    </label>
                  </div>
                  <div className="practice-setting-toggles">
                    <label>
                      <input
                        type="checkbox"
                        checked={draft.documentSettings.header.logo_visible}
                        onChange={(event) =>
                          updateDocumentSettings((settings) => ({
                            ...settings,
                            header: {
                              ...settings.header,
                              logo_visible: event.target.checked,
                            },
                          }))
                        }
                      />
                      Show institution logo
                    </label>
                    <label>
                      <input
                        type="checkbox"
                        checked={draft.documentSettings.questions.show_points}
                        onChange={(event) =>
                          updateDocumentSettings((settings) => ({
                            ...settings,
                            questions: {
                              ...settings.questions,
                              show_points: event.target.checked,
                            },
                          }))
                        }
                      />
                      Show points
                    </label>
                    <label>
                      <input
                        type="checkbox"
                        checked={
                          draft.documentSettings.questions.numbering_enabled
                        }
                        onChange={(event) =>
                          updateDocumentSettings((settings) => ({
                            ...settings,
                            questions: {
                              ...settings.questions,
                              numbering_enabled: event.target.checked,
                            },
                          }))
                        }
                      />
                      Number questions
                    </label>
                  </div>
                  <p className="field-hint">
                    No approved local institution logo is configured; the
                    preview omits it.
                  </p>
                  {draft.entries.length > 0 && (
                    <fieldset className="practice-page-breaks">
                      <legend>Page break before selected questions</legend>
                      {draft.entries.map((entry, index) => {
                        const checked =
                          draft.documentSettings.questions.page_break_before_question_ids.includes(
                            entry.question_id,
                          );
                        return (
                          <label key={entry.question_id}>
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={(event) =>
                                updateDocumentSettings((settings) => ({
                                  ...settings,
                                  questions: {
                                    ...settings.questions,
                                    page_break_before_question_ids: event.target
                                      .checked
                                      ? [
                                          ...settings.questions
                                            .page_break_before_question_ids,
                                          entry.question_id,
                                        ]
                                      : settings.questions.page_break_before_question_ids.filter(
                                          (id) => id !== entry.question_id,
                                        ),
                                  },
                                }))
                              }
                            />
                            Question {index + 1} ·{" "}
                            {questionById.get(entry.question_id)?.title ??
                              `#${entry.question_id}`}
                          </label>
                        );
                      })}
                    </fieldset>
                  )}
                </details>
                <div className="exam-total">
                  <span>{draft.entries.length} selected in the pool</span>
                  <strong>{draft.variants.length} generated variants</strong>
                </div>
                <h3>Question pool</h3>
                {draft.entries.length === 0 ? (
                  <p className="field-hint">
                    Add active questions from the filtered Question Bank.
                  </p>
                ) : (
                  <ol className="quiz-composition">
                    {draft.entries.map((entry, index) => (
                      <li
                        key={entry.question_id}
                        className={
                          draggedQuestionId === entry.question_id
                            ? "practice-question-dragging"
                            : undefined
                        }
                        onDragOver={(event) => {
                          if (!readOnly) event.preventDefault();
                        }}
                        onDrop={() => {
                          if (!readOnly) dropQuestion(entry.question_id);
                          setDraggedQuestionId(null);
                        }}
                      >
                        {!readOnly && (
                          <button
                            type="button"
                            className="practice-drag-handle"
                            draggable
                            aria-label={`Drag question ${index + 1} to reorder`}
                            title="Drag to reorder"
                            onDragStart={(event) => {
                              event.dataTransfer.effectAllowed = "move";
                              event.dataTransfer.setData(
                                "text/plain",
                                String(entry.question_id),
                              );
                              setDraggedQuestionId(entry.question_id);
                            }}
                            onDragEnd={() => setDraggedQuestionId(null)}
                          >
                            <GripVertical size={18} />
                          </button>
                        )}
                        <span>
                          #{entry.question_id} ·{" "}
                          {questionById.get(entry.question_id)?.title ??
                            "Saved question"}
                        </span>
                        <label>
                          Points{" "}
                          <input
                            aria-label={`Points for question ${entry.question_id}`}
                            type="number"
                            min={1}
                            max={1000}
                            value={entry.points ?? ""}
                            onChange={(event) =>
                              replaceEntries(
                                draft.entries.map((item, itemIndex) =>
                                  itemIndex === index
                                    ? {
                                        ...item,
                                        points:
                                          event.target.value === ""
                                            ? null
                                            : Number(event.target.value),
                                      }
                                    : item,
                                ),
                              )
                            }
                          />
                        </label>
                        <button
                          type="button"
                          className="button button-quiet"
                          disabled={index === 0}
                          onClick={() => move(index, -1)}
                        >
                          Up
                        </button>
                        <button
                          type="button"
                          className="button button-quiet"
                          disabled={index === draft.entries.length - 1}
                          onClick={() => move(index, 1)}
                        >
                          Down
                        </button>
                        <button
                          type="button"
                          className="button button-quiet"
                          onClick={() =>
                            replaceEntries(
                              draft.entries.filter(
                                (_, itemIndex) => itemIndex !== index,
                              ),
                            )
                          }
                        >
                          Remove
                        </button>
                      </li>
                    ))}
                  </ol>
                )}
                {!readOnly && (
                  <div className="exam-actions">
                    <button className="button button-primary" type="submit">
                      {busy ? "Saving…" : "Save draft"}
                    </button>
                    {draft.id !== null && (
                      <button
                        className="button button-secondary"
                        type="button"
                        onClick={() => setConfirmingFinalization(true)}
                        disabled={draft.variants.length === 0 || dirty}
                      >
                        Finalize practice sheet
                      </button>
                    )}
                    {dirty && (
                      <span className="field-hint">
                        Save changes before generating variants or finalizing.
                      </span>
                    )}
                  </div>
                )}
              </fieldset>
              {draft.id !== null && (
                <section className="panel" aria-label="Variant generation">
                  <h3>Generate variants</h3>
                  {readOnly ? (
                    <p className="field-hint">
                      Finalized sheets cannot generate further variants.
                    </p>
                  ) : (
                    <>
                      <div className="filters-grid">
                        <label className="field">
                          Variants
                          <input
                            type="number"
                            min={1}
                            max={26}
                            value={variantCount}
                            onChange={(event) =>
                              setVariantCount(Number(event.target.value))
                            }
                          />
                        </label>
                        <label className="field">
                          Questions per variant (optional)
                          <input
                            type="number"
                            min={1}
                            max={draft.entries.length || 1}
                            value={questionsPerVariant}
                            onChange={(event) =>
                              setQuestionsPerVariant(event.target.value)
                            }
                          />
                        </label>
                        <label className="field">
                          Deterministic seed (optional)
                          <input
                            maxLength={120}
                            value={variantSeed}
                            onChange={(event) =>
                              setVariantSeed(event.target.value)
                            }
                          />
                        </label>
                      </div>
                      <button
                        type="button"
                        className="button button-secondary"
                        onClick={() => void generateVariants()}
                        disabled={busy || dirty || draft.entries.length === 0}
                      >
                        Generate variants
                      </button>
                    </>
                  )}
                </section>
              )}
              {draft.id !== null && draft.variants.length === 0 && (
                <section
                  className="panel"
                  aria-label="Practice sheet downloads"
                >
                  <h3>PDF downloads</h3>
                  <p className="field-hint">
                    {dirty
                      ? "Save this draft before generating variants and downloading PDFs."
                      : "Generate at least one variant to enable Student PDF and Answer Key downloads."}
                  </p>
                </section>
              )}
              {draft.variants.length > 0 && (
                <section
                  className="panel"
                  aria-label="Generated variant metadata"
                >
                  <h3>Generated variants</h3>
                  <ul className="quiz-composition">
                    {draft.variants.map((variant) => (
                      <li key={variant.id}>
                        <div>
                          <strong>Version {variant.label}</strong>
                          <span>
                            {variant.question_count} questions ·{" "}
                            {variant.generator_version} · generated{" "}
                            {new Date(variant.generated_at).toLocaleString()}
                          </span>
                        </div>
                        <div className="exam-document-actions">
                          <button
                            type="button"
                            className="button button-secondary"
                            onClick={() => void download(variant.id, "sheet")}
                            disabled={downloading !== null || dirty}
                          >
                            {downloading === `${variant.id}:sheet`
                              ? "Generating…"
                              : "Download Student PDF"}
                          </button>
                          <button
                            type="button"
                            className="button button-secondary"
                            onClick={() =>
                              void download(variant.id, "answer-key")
                            }
                            disabled={downloading !== null || dirty}
                          >
                            {downloading === `${variant.id}:answer-key`
                              ? "Generating…"
                              : "Download Answer Key PDF"}
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                  {dirty && (
                    <p className="field-hint">
                      Save changes before downloading so the PDF uses the
                      current document settings.
                    </p>
                  )}
                </section>
              )}
            </form>
            <aside className="exam-picker">
              <h2>Add questions</h2>
              {metadataError && (
                <p className="error-message" role="alert">
                  Could not load filters: {metadataError}
                </p>
              )}
              {metadata && (
                <QuestionFilters
                  metadata={metadata}
                  onApply={(next) => {
                    setLoadingQuestions(true);
                    setFilters(next);
                    setOffset(0);
                  }}
                />
              )}
              {readOnly ? (
                <p className="field-hint">
                  Finalized practice sheets cannot be changed.
                </p>
              ) : loadingQuestions ? (
                <p role="status">Loading matching questions…</p>
              ) : groups.length === 0 ? (
                <p>No questions match these filters.</p>
              ) : (
                <div className="quiz-bank-picker">
                  {groups.map((group) => (
                    <details className="topic-accordion" key={group.label} open>
                      <summary>
                        <span>{group.label}</span>
                        <span className="topic-group-count">
                          {group.items.length}
                        </span>
                        <ChevronDown size={17} />
                      </summary>
                      <div className="quiz-topic-items">
                        {group.items.map((question) => (
                          <div key={question.id}>
                            <span>
                              #{question.id} ·{" "}
                              {question.title ?? question.question_text}
                              {!question.is_active ? " (inactive)" : ""}
                            </span>
                            <button
                              type="button"
                              className="button button-secondary"
                              disabled={
                                !question.is_active ||
                                draft.entries.some(
                                  (entry) => entry.question_id === question.id,
                                ) ||
                                draft.entries.length >= 100
                              }
                              onClick={() => add(question)}
                            >
                              Add
                            </button>
                          </div>
                        ))}
                      </div>
                    </details>
                  ))}
                </div>
              )}
              <div className="quiz-actions">
                <button
                  type="button"
                  className="button button-secondary"
                  disabled={offset === 0 || loadingQuestions}
                  onClick={() => {
                    setLoadingQuestions(true);
                    setOffset(Math.max(0, offset - PAGE_SIZE));
                  }}
                >
                  Previous
                </button>
                <button
                  type="button"
                  className="button button-secondary"
                  disabled={offset + PAGE_SIZE >= total || loadingQuestions}
                  onClick={() => {
                    setLoadingQuestions(true);
                    setOffset(offset + PAGE_SIZE);
                  }}
                >
                  Next
                </button>
              </div>
            </aside>
          </section>
        </div>
        <aside
          className="practice-sheet-preview-pane"
          aria-label="Live practice sheet preview"
        >
          <header className="practice-sheet-preview-toolbar">
            <h2>Draft Preview</h2>
            <p className="draft-save-state" role="status">
              {readOnly
                ? "Finalized sheet — read-only preview"
                : dirty
                  ? "Unsaved changes — preview only"
                  : "Saved draft"}
            </p>
            <p>
              This HTML preview follows the current editor. PDF output remains
              authoritative.
            </p>
          </header>
          <div
            className="practice-sheet-preview-scroll"
            tabIndex={0}
            aria-label="Scrollable practice sheet preview"
          >
            <article
              className={`draft-paper practice-sheet-paper practice-sheet-margins-${draft.documentSettings.layout.margins}`}
            >
              <header className="practice-sheet-paper-heading">
                {draft.documentSettings.header.logo_visible && (
                  <span
                    className="practice-logo-unavailable"
                    title="No approved local logo asset is configured"
                  >
                    Logo unavailable
                  </span>
                )}
                <strong>
                  {draft.documentSettings.header.institution_name}
                </strong>
                <h2>{draft.documentSettings.header.course_name}</h2>
                <h3>{draft.title.trim() || "Untitled Practice Sheet"}</h3>
                {(draft.documentSettings.header.instructor_name ||
                  draft.documentSettings.header.document_date) && (
                  <p>
                    {draft.documentSettings.header.instructor_name &&
                      `Instructor: ${draft.documentSettings.header.instructor_name}`}
                    {draft.documentSettings.header.instructor_name &&
                      draft.documentSettings.header.document_date &&
                      " · "}
                    {draft.documentSettings.header.document_date &&
                      `Date: ${draft.documentSettings.header.document_date}`}
                  </p>
                )}
                <p>Draft question pool</p>
              </header>
              <p className="practice-sheet-identity">
                <strong>Name:</strong> ____________________{" "}
                <strong>Neptun code:</strong> ____________{" "}
                <strong>Date:</strong> ____________
              </p>
              {draft.instructions.trim() && (
                <p className="draft-paragraph">
                  <MathText text={draft.instructions} />
                </p>
              )}
              {draft.entries.length === 0 ? (
                <p className="field-hint">
                  Add questions to see the printable draft.
                </p>
              ) : (
                <ol
                  className={`practice-sheet-preview-questions practice-sheet-spacing-${draft.documentSettings.layout.question_spacing} ${draft.documentSettings.questions.numbering_enabled ? "" : "practice-sheet-no-numbering"}`}
                >
                  {draft.entries.map((entry, index) => {
                    const question = questionById.get(entry.question_id);
                    const pageBreak =
                      draft.documentSettings.questions.page_break_before_question_ids.includes(
                        entry.question_id,
                      );
                    return (
                      <li
                        key={entry.question_id}
                        className={
                          pageBreak ? "practice-sheet-page-break" : undefined
                        }
                      >
                        {pageBreak && (
                          <span className="practice-sheet-page-break-label">
                            Page break before this question
                          </span>
                        )}
                        <div className="practice-sheet-question-heading">
                          {draft.documentSettings.questions
                            .numbering_enabled && (
                            <strong>Question {index + 1}</strong>
                          )}
                          {draft.documentSettings.questions.show_points &&
                            entry.points !== null && (
                              <span>{entry.points} points</span>
                            )}
                        </div>
                        {question ? (
                          <MathText text={question.question_text} />
                        ) : (
                          <span className="field-hint">
                            Loading question {entry.question_id}…
                          </span>
                        )}
                        <div
                          className={`practice-sheet-answer-space practice-sheet-answer-space-${draft.documentSettings.questions.answer_space}`}
                          aria-hidden="true"
                        />
                      </li>
                    );
                  })}
                </ol>
              )}
            </article>
          </div>
        </aside>
      </section>
      {confirmingFinalization && (
        <section
          className="panel exam-confirmation"
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="finalize-title"
        >
          <h2 id="finalize-title">Finalize this practice sheet?</h2>
          <p>
            This freezes the current generated variants. They cannot be changed
            or replaced afterward.
          </p>
          <div className="exam-actions">
            <button
              className="button button-secondary"
              type="button"
              onClick={() => setConfirmingFinalization(false)}
              disabled={busy}
            >
              Cancel
            </button>
            <button
              className="button button-primary"
              type="button"
              onClick={() => void finalize()}
              disabled={busy}
            >
              {busy ? "Finalizing…" : "Finalize practice sheet"}
            </button>
          </div>
        </section>
      )}
    </>
  );
}

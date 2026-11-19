"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronDown, Plus, RefreshCw, Trash2 } from "lucide-react";

import {
  downloadExamLatex,
  downloadExamPdf,
  defaultExamDocumentSettings,
  examsApi,
  getExamPdf,
  type ExamDocumentSettings,
  type Exam,
  type ExamEntry,
} from "@/lib/exams";
import {
  questionsApi,
  type Question,
  type QuestionFilters as Filters,
} from "@/lib/questions";
import { orderedTopics, useMetadata } from "@/lib/use-metadata";
import { useAuth } from "./auth-provider";
import { PageHeading } from "./page-heading";
import { QuestionFilters } from "./question-filters";
import { PdfPreviewDialog } from "./pdf-preview-dialog";
import { PdfPreviewPanel } from "./pdf-preview-panel";

const PAGE_SIZE = 20;
const emptyDraft = () => ({
  id: null as number | null,
  title: "",
  instructions: "",
  status: "draft" as Exam["status"],
  entries: [] as ExamEntry[],
  documentSettings: defaultExamDocumentSettings(),
});
const signature = (draft: ReturnType<typeof emptyDraft>) =>
  JSON.stringify({
    title: draft.title,
    instructions: draft.instructions,
    entries: draft.entries.map(({ question_id, points }) => ({
      question_id,
      points,
    })),
    documentSettings: draft.documentSettings,
  });

export function ExamBuilder() {
  const { user } = useAuth();
  const [exams, setExams] = useState<Exam[]>([]);
  const [draft, setDraft] = useState(emptyDraft);
  const [savedSignature, setSavedSignature] = useState("");
  const [questions, setQuestions] = useState<Question[]>([]);
  const [filters, setFilters] = useState<Filters>({});
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingQuestions, setLoadingQuestions] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [confirmingFinalization, setConfirmingFinalization] = useState(false);
  const [downloading, setDownloading] = useState<"exam" | "answer-key" | null>(
    null,
  );
  const [exportingLatex, setExportingLatex] = useState<
    "exam" | "answer-key" | null
  >(null);
  const [previewKind, setPreviewKind] = useState<"exam" | "answer-key" | null>(
    null,
  );
  const [workspacePreviewKind, setWorkspacePreviewKind] = useState<
    "exam" | "answer-key"
  >("exam");
  const { metadata, error: metadataError } = useMetadata();
  const readOnly = draft.status === "finalized";
  const dirty =
    draft.id !== null && !readOnly && signature(draft) !== savedSignature;

  const fetchExams = () => {
    void examsApi
      .list()
      .then((items) => {
        setExams(items);
        setLoading(false);
      })
      .catch((reason: Error) => {
        setError(reason.message);
        setLoading(false);
      });
  };
  const loadExams = () => {
    setLoading(true);
    setError("");
    fetchExams();
  };
  useEffect(() => {
    fetchExams();
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

  const questionById = useMemo(
    () => new Map(questions.map((question) => [question.id, question])),
    [questions],
  );
  const totalPoints = draft.entries.reduce(
    (sum, entry) => sum + entry.points,
    0,
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

  function open(exam: Exam) {
    const next = {
      id: exam.id,
      title: exam.title,
      instructions: exam.instructions ?? "",
      status: exam.status,
      entries: exam.questions,
      documentSettings: exam.document_settings,
    };
    setDraft(next);
    setSavedSignature(signature(next));
    setConfirmingFinalization(false);
    setPreviewKind(null);
    setNotice("");
    setError("");
  }
  function replaceEntries(entries: ExamEntry[]) {
    setDraft((current) => ({
      ...current,
      entries: entries.map((entry, position) => ({ ...entry, position })),
    }));
  }
  function updateDocumentSettings(
    update: (settings: ExamDocumentSettings) => ExamDocumentSettings,
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
    replaceEntries([
      ...draft.entries,
      { question_id: question.id, points: 1, position: draft.entries.length },
    ]);
  }
  function move(index: number, delta: number) {
    const next = [...draft.entries];
    [next[index], next[index + delta]] = [next[index + delta], next[index]];
    replaceEntries(next);
  }
  async function save() {
    if (busy || readOnly) return;
    if (!draft.title.trim())
      return setError("Enter an exam title before saving.");
    if (
      draft.entries.some(
        (entry) =>
          !Number.isInteger(entry.points) ||
          entry.points < 1 ||
          entry.points > 1000,
      )
    )
      return setError("Each question must have 1–1000 whole points.");
    setBusy(true);
    setError("");
    try {
      const body = {
        title: draft.title.trim(),
        instructions: draft.instructions.trim() || null,
        document_settings: draft.documentSettings,
        questions: draft.entries.map(({ question_id, points }) => ({
          question_id,
          points,
        })),
      };
      const saved =
        draft.id === null
          ? await examsApi.create(body)
          : await examsApi.update(draft.id, body);
      open(saved);
      setExams((items) => [
        saved,
        ...items.filter((item) => item.id !== saved.id),
      ]);
      setNotice("Draft saved.");
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Could not save this exam.",
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
      const finalized = await examsApi.finalize(draft.id);
      open(finalized);
      setExams((items) =>
        items.map((item) => (item.id === finalized.id ? finalized : item)),
      );
      setNotice("Exam finalized. Its question snapshot is now immutable.");
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not finalize this exam.",
      );
    } finally {
      setBusy(false);
      setConfirmingFinalization(false);
    }
  }
  async function remove(exam: Exam) {
    if (
      exam.status !== "draft" ||
      busy ||
      !window.confirm(`Delete draft “${exam.title}”?`)
    )
      return;
    setBusy(true);
    setError("");
    try {
      await examsApi.remove(exam.id);
      setExams((items) => items.filter((item) => item.id !== exam.id));
      if (draft.id === exam.id) {
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
  async function download(kind: "exam" | "answer-key") {
    if (draft.id === null || downloading || exportingLatex) return;
    if (dirty) {
      setError(
        "You have unsaved changes. Please save before downloading a PDF.",
      );
      return;
    }
    setDownloading(kind);
    setError("");
    try {
      await downloadExamPdf(draft.id, kind);
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
  async function downloadLatex(kind: "exam" | "answer-key") {
    if (draft.id === null || downloading || exportingLatex) return;
    if (dirty) {
      setError("You have unsaved changes. Please save before exporting LaTeX.");
      return;
    }
    setExportingLatex(kind);
    setError("");
    try {
      await downloadExamLatex(draft.id, kind);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not export this LaTeX source.",
      );
    } finally {
      setExportingLatex(null);
    }
  }
  function preview(kind: "exam" | "answer-key") {
    if (draft.id === null || dirty) {
      setError(
        "You have unsaved changes. Please save before previewing a PDF.",
      );
      return;
    }
    setError("");
    setPreviewKind(kind);
  }
  const previewDocument =
    draft.id !== null && previewKind !== null
      ? { id: draft.id, kind: previewKind }
      : null;

  return (
    <>
      <PageHeading
        eyebrow="TEACHING RESOURCES"
        title="Exam Builder"
        description="Compose controlled printable assessments from the verified course question bank."
        action={
          <button
            className="button button-primary"
            onClick={() => {
              setDraft(emptyDraft());
              setSavedSignature("");
            }}
          >
            <Plus size={17} />
            New exam
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
      <section className="panel exam-list" aria-label="Saved exams">
        <div className="panel-heading">
          <div>
            <h2>Saved exams</h2>
            <p>
              Drafts remain editable; finalized exams are preserved for print
              generation.
            </p>
          </div>
          <button
            className="button button-quiet"
            onClick={loadExams}
            disabled={loading}
          >
            <RefreshCw size={16} className={loading ? "spin" : ""} />
            Refresh
          </button>
        </div>
        {loading ? (
          <p role="status">Loading exams…</p>
        ) : exams.length === 0 ? (
          <p>No exams yet. Start a draft to compose your first assessment.</p>
        ) : (
          <div className="exam-list-items">
            {exams.map((exam) => (
              <article
                key={exam.id}
                className={
                  draft.id === exam.id ? "exam-row selected" : "exam-row"
                }
              >
                <button
                  type="button"
                  className="exam-open"
                  onClick={() => open(exam)}
                >
                  <strong>{exam.title}</strong>
                  <span className={`exam-status ${exam.status}`}>
                    {exam.status}
                  </span>
                  <span>
                    {exam.questions.length} question
                    {exam.questions.length === 1 ? "" : "s"} ·{" "}
                    {exam.questions.reduce(
                      (sum, entry) => sum + entry.points,
                      0,
                    )}{" "}
                    points
                  </span>
                </button>
                {exam.status === "draft" && (
                  <button
                    type="button"
                    className="icon-button"
                    aria-label={`Delete ${exam.title}`}
                    onClick={() => void remove(exam)}
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
      <section className="exam-builder-workspace">
        <section className="exam-builder-grid">
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
                    ? "New exam"
                    : readOnly
                      ? "Finalized exam"
                      : "Edit draft"}
                </h2>
                <p>
                  {readOnly
                    ? "This saved composition is read-only."
                    : "Set the assessment details and question order."}
                </p>
              </div>
              {draft.id !== null && (
                <div className="exam-document-actions">
                  <span className={`exam-status ${draft.status}`}>
                    {draft.status}
                  </span>
                  <button
                    className="button button-secondary"
                    type="button"
                    onClick={() => preview("exam")}
                    disabled={
                      downloading !== null || exportingLatex !== null || dirty
                    }
                  >
                    Preview Exam PDF
                  </button>
                  <button
                    className="button button-secondary"
                    type="button"
                    onClick={() => void download("exam")}
                    disabled={
                      downloading !== null || exportingLatex !== null || dirty
                    }
                  >
                    {downloading === "exam"
                      ? "Generating exam…"
                      : "Download Exam PDF"}
                  </button>
                  <button
                    className="button button-secondary"
                    type="button"
                    onClick={() => void downloadLatex("exam")}
                    disabled={
                      downloading !== null || exportingLatex !== null || dirty
                    }
                  >
                    {exportingLatex === "exam"
                      ? "Exporting LaTeX…"
                      : "Download Exam LaTeX (.tex)"}
                  </button>
                  <button
                    className="button button-secondary"
                    type="button"
                    onClick={() => preview("answer-key")}
                    disabled={
                      downloading !== null || exportingLatex !== null || dirty
                    }
                  >
                    Preview Answer Key PDF
                  </button>
                  <button
                    className="button button-secondary"
                    type="button"
                    onClick={() => void download("answer-key")}
                    disabled={
                      downloading !== null || exportingLatex !== null || dirty
                    }
                  >
                    {downloading === "answer-key"
                      ? "Generating key…"
                      : "Download Answer Key PDF"}
                  </button>
                  <button
                    className="button button-secondary"
                    type="button"
                    onClick={() => void downloadLatex("answer-key")}
                    disabled={
                      downloading !== null || exportingLatex !== null || dirty
                    }
                  >
                    {exportingLatex === "answer-key"
                      ? "Exporting LaTeX…"
                      : "Download Answer Key LaTeX (.tex)"}
                  </button>
                </div>
              )}
            </div>
            {dirty && (
              <p className="field-hint">
                Save changes before downloading so the PDF matches this draft.
              </p>
            )}
            <fieldset disabled={busy || readOnly}>
              <label className="field">
                Exam title
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
                <summary>Document settings</summary>
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
                    Course title
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
                    Instructor (optional)
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
                    Exam date (optional)
                    <input
                      type="date"
                      value={draft.documentSettings.header.document_date ?? ""}
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
                    Duration in minutes (optional)
                    <input
                      type="number"
                      min={1}
                      max={600}
                      value={
                        draft.documentSettings.header.duration_minutes ?? ""
                      }
                      onChange={(event) =>
                        updateDocumentSettings((settings) => ({
                          ...settings,
                          header: {
                            ...settings.header,
                            duration_minutes: event.target.value
                              ? Number(event.target.value)
                              : null,
                          },
                        }))
                      }
                    />
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
                              .value as ExamDocumentSettings["layout"]["margins"],
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
                              .value as ExamDocumentSettings["layout"]["question_spacing"],
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
                              .value as ExamDocumentSettings["questions"]["answer_space"],
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
                  {[
                    ["layout", "page_numbering", "Show page numbers"],
                    ["questions", "show_points", "Show points"],
                    ["questions", "numbering_enabled", "Number questions"],
                    ["student_fields", "show_name", "Student name field"],
                    ["student_fields", "show_neptun_code", "Neptun code field"],
                    ["student_fields", "show_date", "Student date field"],
                  ].map(([group, key, label]) => {
                    const value = draft.documentSettings[
                      group as keyof ExamDocumentSettings
                    ][key as never] as boolean;
                    return (
                      <label key={`${group}-${key}`}>
                        <input
                          type="checkbox"
                          checked={value}
                          onChange={(event) =>
                            updateDocumentSettings((settings) => ({
                              ...settings,
                              [group]: {
                                ...settings[
                                  group as keyof ExamDocumentSettings
                                ],
                                [key]: event.target.checked,
                              },
                            }))
                          }
                        />
                        {label}
                      </label>
                    );
                  })}
                </div>
              </details>
              <div className="exam-total">
                <span>{draft.entries.length} selected</span>
                <strong>{totalPoints} total points</strong>
              </div>
              <h3>Questions in print order</h3>
              {draft.entries.length > 0 && (
                <fieldset className="practice-page-breaks">
                  <legend>Page break before selected questions</legend>
                  {draft.entries.map((entry, index) => {
                    const checked =
                      draft.documentSettings.questions.page_break_before_question_ids.includes(
                        entry.question_id,
                      );
                    return (
                      <label key={`page-break-${entry.question_id}`}>
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
                        Question {index + 1}
                      </label>
                    );
                  })}
                </fieldset>
              )}
              {draft.entries.length === 0 ? (
                <p className="field-hint">
                  Add active questions from the filtered Question Bank.
                </p>
              ) : (
                <ol className="quiz-composition">
                  {draft.entries.map((entry, index) => (
                    <li key={entry.question_id}>
                      <span>
                        #{entry.question_id} ·{" "}
                        {questionById.get(entry.question_id)?.title ??
                          "Saved question"}
                      </span>
                      <label>
                        Points
                        <input
                          aria-label={`Points for question ${entry.question_id}`}
                          type="number"
                          min={1}
                          max={1000}
                          required
                          value={entry.points}
                          onChange={(event) =>
                            replaceEntries(
                              draft.entries.map((item, itemIndex) =>
                                itemIndex === index
                                  ? {
                                      ...item,
                                      points: Number(event.target.value),
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
                      disabled={draft.entries.length === 0 || dirty}
                    >
                      Finalize exam
                    </button>
                  )}
                  {dirty && (
                    <span className="field-hint">
                      Save changes before finalizing.
                    </span>
                  )}
                </div>
              )}
            </fieldset>
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
              <p className="field-hint">Finalized exams cannot be changed.</p>
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
        <aside className="exam-pdf-workspace" aria-label="Exam PDF preview">
          <div
            className="exam-pdf-kind-tabs"
            role="group"
            aria-label="PDF type"
          >
            <button
              type="button"
              aria-pressed={workspacePreviewKind === "exam"}
              className={workspacePreviewKind === "exam" ? "active" : ""}
              onClick={() => setWorkspacePreviewKind("exam")}
            >
              Student exam
            </button>
            <button
              type="button"
              aria-pressed={workspacePreviewKind === "answer-key"}
              className={workspacePreviewKind === "answer-key" ? "active" : ""}
              onClick={() => setWorkspacePreviewKind("answer-key")}
            >
              Answer key
            </button>
          </div>
          <PdfPreviewPanel
            key={`exam:${draft.id ?? "new"}:${workspacePreviewKind}:${dirty ? "dirty" : savedSignature}`}
            title={
              workspacePreviewKind === "exam"
                ? "Student exam PDF"
                : "Exam answer key PDF"
            }
            disabled={draft.id === null || dirty || downloading !== null}
            disabledMessage={
              draft.id === null
                ? "Save the draft before generating its authoritative PDF."
                : dirty
                  ? "Save changes before previewing so this PDF matches the current draft."
                  : "Another document is being prepared."
            }
            loadPdf={(signal) =>
              getExamPdf(draft.id!, workspacePreviewKind, signal)
            }
            onFullscreen={() => preview(workspacePreviewKind)}
          />
        </aside>
      </section>
      {confirmingFinalization && (
        <section
          className="panel exam-confirmation"
          aria-labelledby="finalize-title"
        >
          <h2 id="finalize-title">Finalize this exam?</h2>
          <p>
            This permanently freezes the selected questions and answer material.
            It cannot be edited or deleted afterward.
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
              {busy ? "Finalizing…" : "Finalize exam"}
            </button>
          </div>
        </section>
      )}
      {previewDocument && (
        <PdfPreviewDialog
          open
          title={
            previewDocument.kind === "exam"
              ? "Exam PDF preview"
              : "Exam Answer Key PDF preview"
          }
          documentKey={`exam:${previewDocument.id}:${previewDocument.kind}`}
          loadPdf={(signal) =>
            getExamPdf(previewDocument.id, previewDocument.kind, signal)
          }
          onClose={() => setPreviewKind(null)}
        />
      )}
    </>
  );
}

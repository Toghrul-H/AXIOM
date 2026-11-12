"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronDown, Plus, RefreshCw, Trash2 } from "lucide-react";

import {
  downloadExamPdf,
  examsApi,
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

const PAGE_SIZE = 20;
const emptyDraft = () => ({
  id: null as number | null,
  title: "",
  instructions: "",
  status: "draft" as Exam["status"],
  entries: [] as ExamEntry[],
});
const signature = (draft: ReturnType<typeof emptyDraft>) =>
  JSON.stringify({
    title: draft.title,
    instructions: draft.instructions,
    entries: draft.entries.map(({ question_id, points }) => ({
      question_id,
      points,
    })),
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
    };
    setDraft(next);
    setSavedSignature(signature(next));
    setConfirmingFinalization(false);
    setNotice("");
    setError("");
  }
  function replaceEntries(entries: ExamEntry[]) {
    setDraft((current) => ({
      ...current,
      entries: entries.map((entry, position) => ({ ...entry, position })),
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
    if (draft.id === null || downloading) return;
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
                  onClick={() => void download("exam")}
                  disabled={downloading !== null}
                >
                  {downloading === "exam"
                    ? "Generating exam…"
                    : "Download Exam PDF"}
                </button>
                <button
                  className="button button-secondary"
                  type="button"
                  onClick={() => void download("answer-key")}
                  disabled={downloading !== null}
                >
                  {downloading === "answer-key"
                    ? "Generating key…"
                    : "Download Answer Key PDF"}
                </button>
              </div>
            )}
          </div>
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
            <div className="exam-total">
              <span>{draft.entries.length} selected</span>
              <strong>{totalPoints} total points</strong>
            </div>
            <h3>Questions in print order</h3>
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
      {confirmingFinalization && (
        <section
          className="panel exam-confirmation"
          role="alertdialog"
          aria-modal="true"
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
    </>
  );
}

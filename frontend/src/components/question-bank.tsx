"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
  X,
} from "lucide-react";
import {
  Question,
  QuestionFilters as Filters,
  questionsApi,
  typeLabels,
} from "@/lib/questions";
import { orderedTopics, useMetadata } from "@/lib/use-metadata";
import { QuestionFilters } from "./question-filters";
import { PageHeading } from "./page-heading";

const PAGE_SIZE = 12;

export function QuestionBank() {
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState<Filters>({});
  const { metadata, error: metadataError } = useMetadata();
  const [revision, setRevision] = useState(0);
  const [rows, setRows] = useState<Question[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [pendingDelete, setPendingDelete] = useState<Question | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const cancelButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    questionsApi
      .list(page * PAGE_SIZE, PAGE_SIZE, controller.signal, filters)
      .then((data) => {
        setRows(data.items);
        setTotal(data.total);
        setLoading(false);
      })
      .catch((e: Error) => {
        if (e.name !== "AbortError") {
          setError(e.message);
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [page, revision, filters]);

  function applyFilters(value: Filters) {
    setLoading(true);
    setError("");
    setPage(0);
    setFilters({ ...value });
  }

  function reload() {
    setLoading(true);
    setError("");
    setRevision((value) => value + 1);
  }
  function changePage(value: number) {
    setLoading(true);
    setError("");
    setPage(value);
  }
  function confirmDelete(question: Question) {
    setPendingDelete(question);
    setDeleteError("");
    dialog.current?.showModal();
    cancelButton.current?.focus();
  }
  async function remove() {
    if (!pendingDelete || deleting) return;
    setDeleting(true);
    setDeleteError("");
    try {
      await questionsApi.remove(pendingDelete.id);
      dialog.current?.close();
      setPendingDelete(null);
      setNotice(`Question #${pendingDelete.id} deleted.`);
      if (rows.length === 1 && page > 0) changePage(page - 1);
      else reload();
    } catch (e) {
      setDeleteError(
        e instanceof Error ? e.message : "Could not delete question.",
      );
    } finally {
      setDeleting(false);
    }
  }

  const topicMap = new Map(
    (metadata?.topics ?? []).map((topic) => [topic.id, topic]),
  );
  for (const question of rows) topicMap.set(question.topic.id, question.topic);
  const groups = orderedTopics([...topicMap.values()])
    .map(({ topic }) => ({
      topic,
      questions: rows.filter((q) => q.topic.id === topic.id),
    }))
    .filter((group) => group.questions.length > 0);

  return (
    <>
      <PageHeading
        eyebrow="TEACHING RESOURCES"
        title="Question Bank"
        description="A growing collection of ideas, problems, and explanations."
        action={
          <Link href="/teacher/questions/new" className="button button-primary">
            <Plus size={17} />
            Add question
          </Link>
        }
      />
      {metadataError && (
        <div role="alert" className="error-message">
          Could not load filters: {metadataError}
        </div>
      )}
      {metadata && (
        <QuestionFilters metadata={metadata} onApply={applyFilters} />
      )}
      <div className="bank-toolbar">
        <div>
          <span className="live-dot" />
          <strong>Course collection</strong>
          <span className="muted small">Saved in your course database</span>
        </div>
        <button
          className="button button-quiet"
          onClick={reload}
          disabled={loading}
        >
          <RefreshCw size={15} className={loading ? "spin" : ""} />
          Refresh
        </button>
      </div>
      {notice && (
        <div className="success-message" role="status">
          <CheckCircle2 size={18} />
          {notice}
          <button
            className="icon-button"
            aria-label="Dismiss notification"
            onClick={() => setNotice("")}
          >
            <X size={16} />
          </button>
        </div>
      )}
      {error ? (
        <div className="panel error-state" role="alert">
          <h2>We couldn’t load your questions.</h2>
          <p>{error}</p>
          <button className="button button-secondary" onClick={reload}>
            Try again
          </button>
        </div>
      ) : loading ? (
        <div className="panel loading-state" role="status">
          <RefreshCw className="spin" size={22} />
          <p>Loading your question bank…</p>
        </div>
      ) : rows.length === 0 ? (
        <section className="panel empty-state">
          <BookOpen size={38} />
          <h2>
            {page
              ? "You’ve reached the end."
              : Object.values(filters).some(Boolean)
                ? "No questions match these filters."
                : "A blank page, full of possibilities."}
          </h2>
          <p>
            {page
              ? "There are no more questions in this collection."
              : Object.values(filters).some(Boolean)
                ? "Adjust or clear the filters to see more questions."
                : "Add your first question and start building a resource for your course."}
          </p>
          {page ? (
            <button
              className="button button-secondary"
              onClick={() => changePage(page - 1)}
            >
              <ArrowLeft size={16} />
              Previous page
            </button>
          ) : (
            <Link
              href="/teacher/questions/new"
              className="button button-primary"
            >
              <Plus size={16} />
              Create first question
            </Link>
          )}
        </section>
      ) : (
        <>
          <div className="question-list">
            <p className="field-hint">
              Grouped by primary course topic · counts reflect this filtered
              page.
            </p>
            {groups.map(({ topic, questions }, index) => (
              <section key={topic.id} className="topic-group-section">
                {topic.parent &&
                  groups[index - 1]?.topic.parent?.id !== topic.parent.id && (
                    <h2 className="topic-parent-heading">
                      {topic.parent.name}
                    </h2>
                  )}
                <details className="topic-accordion" open>
                  <summary>
                    <span>{topic.name}</span>
                    <span className="topic-group-count">
                      {questions.length}{" "}
                      {questions.length === 1 ? "question" : "questions"}
                    </span>
                    <ChevronDown size={17} />
                  </summary>
                  <div className="topic-group-questions">
                    {questions.map((question) => (
                      <article className="question-card" key={question.id}>
                        <div className="question-card-heading">
                          <div className="question-tags">
                            <span className="topic-tag">
                              {question.topic.parent
                                ? `${question.topic.parent.name} / `
                                : ""}
                              {question.topic.name}
                            </span>
                            <span
                              className={`difficulty ${question.difficulty}`}
                            >
                              {question.difficulty}
                            </span>
                            <span className="type-tag">
                              {typeLabels[question.response_type]}
                            </span>
                            <span className="type-tag">
                              {metadata?.skill_types.find(
                                (s) => s.code === question.skill_type,
                              )?.label ?? question.skill_type}
                            </span>
                            {!question.is_active && (
                              <span className="difficulty hard">Inactive</span>
                            )}
                          </div>
                          <span className="question-id">#{question.id}</span>
                        </div>
                        {question.title && (
                          <p className="question-title">{question.title}</p>
                        )}
                        <h2>{question.question_text}</h2>
                        <div className="association-tags">
                          {question.problem_sets.map((p) => (
                            <span key={p.id}>{p.code}</span>
                          ))}
                          {question.assessment_suitabilities.map((tag) => (
                            <span key={tag.code}>{tag.label}</span>
                          ))}
                        </div>
                        {question.options.length > 0 && (
                          <ul className="answer-options">
                            {question.options.map((option, index) => (
                              <li key={option.id}>
                                <span>{String.fromCharCode(65 + index)}</span>
                                {option.text}
                              </li>
                            ))}
                          </ul>
                        )}
                        <details className="solution">
                          <summary>
                            <BookOpen size={15} />
                            Answer & explanation
                            <ChevronDown size={15} />
                          </summary>
                          <div>
                            <p className="eyebrow">CORRECT ANSWER</p>
                            {question.response_type === "FREE_RESPONSE" ? (
                              <>
                                <p className="answer-text">
                                  {question.expected_answer}
                                </p>
                                <p className="field-hint">
                                  Reference only · not automatically graded
                                </p>
                              </>
                            ) : question.response_type === "TRUE_FALSE" ? (
                              <p className="answer-text">
                                {question.correct_boolean ? "True" : "False"}
                              </p>
                            ) : (
                              <ul className="correct-answer-list">
                                {question.options
                                  .filter((o) => o.is_correct)
                                  .map((o) => (
                                    <li key={o.id}>{o.text}</li>
                                  ))}
                              </ul>
                            )}
                            {question.explanation && (
                              <>
                                <p className="eyebrow">EXPLANATION</p>
                                <p>{question.explanation}</p>
                              </>
                            )}
                          </div>
                        </details>
                        <div className="question-card-bottom">
                          <span>
                            Added{" "}
                            {new Date(question.created_at).toLocaleDateString(
                              "en-GB",
                              {
                                day: "numeric",
                                month: "short",
                                year: "numeric",
                              },
                            )}
                          </span>
                          <div>
                            <Link
                              href={`/teacher/questions/${question.id}/edit`}
                              className="button button-quiet"
                              aria-label={`Edit question ${question.id}`}
                            >
                              <Pencil size={15} />
                              Edit
                            </Link>
                            <button
                              className="button button-quiet delete-button"
                              onClick={() => confirmDelete(question)}
                              aria-label={`Delete question ${question.id}`}
                            >
                              <Trash2 size={15} />
                              Delete
                            </button>
                          </div>
                        </div>
                      </article>
                    ))}
                  </div>
                </details>
              </section>
            ))}
          </div>
          <div className="pagination">
            <p>
              Showing {page * PAGE_SIZE + 1}–{page * PAGE_SIZE + rows.length}{" "}
              <span className="muted">
                of {total} · Page {page + 1}
              </span>
            </p>
            <div>
              <button
                className="button button-secondary"
                disabled={page === 0}
                onClick={() => changePage(page - 1)}
              >
                <ArrowLeft size={15} />
                Previous
              </button>
              <button
                className="button button-secondary"
                disabled={(page + 1) * PAGE_SIZE >= total}
                onClick={() => changePage(page + 1)}
              >
                Next
                <ArrowRight size={15} />
              </button>
            </div>
          </div>
        </>
      )}
      <dialog
        ref={dialog}
        className="delete-dialog"
        aria-labelledby="delete-title"
        aria-describedby="delete-description"
        onCancel={(e) => {
          if (deleting) e.preventDefault();
        }}
      >
        <span className="delete-symbol">
          <Trash2 size={24} />
        </span>
        <h2 id="delete-title">Delete this question?</h2>
        <p id="delete-description">
          Question #{pendingDelete?.id} will be permanently removed from the
          course collection. This cannot be undone.
        </p>
        <blockquote>{pendingDelete?.question_text}</blockquote>
        {deleteError && (
          <p role="alert" className="error-message">
            {deleteError}
          </p>
        )}
        <div className="dialog-actions">
          <button
            ref={cancelButton}
            className="button button-secondary"
            disabled={deleting}
            onClick={() => dialog.current?.close()}
          >
            Keep question
          </button>
          <button
            className="button button-danger"
            disabled={deleting}
            onClick={remove}
          >
            {deleting ? "Deleting…" : "Delete question"}
          </button>
        </div>
      </dialog>
    </>
  );
}

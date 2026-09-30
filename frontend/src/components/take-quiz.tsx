"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Answer, Attempt, AttemptItem, quizzesApi } from "@/lib/quizzes";
import { PageHeading } from "./page-heading";
import { MathAnswerInput } from "./math-answer-input";
import { mathProfileForTopic } from "@/lib/math-symbols";
const emptyAnswer: Answer = {
  selected_option_ids: [],
  boolean_answer: null,
  free_response: null,
};
const isAnswered = (a: Answer) =>
  a.selected_option_ids.length > 0 ||
  a.boolean_answer !== null ||
  !!a.free_response?.trim();

export function TakeQuiz({ id }: { id: string }) {
  const router = useRouter();
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    quizzesApi
      .attempt(id)
      .then((a) => {
        if (!live) return;
        if (a.status === "SUBMITTED")
          router.replace(`/student/quizzes/attempts/${id}/results`);
        else setAttempt(a);
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [id, router]);
  if (error)
    return (
      <p role="alert" className="error-message">
        {error} <Link href="/student/quizzes">Back to quizzes</Link>
      </p>
    );
  if (!attempt) return <p role="status">Loading saved attempt…</p>;
  return <QuizRunner initial={attempt} />;
}
function QuizRunner({ initial }: { initial: Attempt }) {
  const router = useRouter();
  const [index, setIndex] = useState(0);
  const [items, setItems] = useState(initial.items);
  const [draft, setDraft] = useState<Answer>(initial.items[0]);
  const [dirty, setDirty] = useState(false);
  const [status, setStatus] = useState("Saved");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const revision = useRef(0);
  const queue = useRef<Promise<unknown>>(Promise.resolve());
  const dialog = useRef<HTMLDialogElement>(null);
  const continueButton = useRef<HTMLButtonElement>(null);
  const item = items[index];
  function change(answer: Answer) {
    revision.current += 1;
    setDraft(answer);
    setDirty(true);
    setStatus("Not saved yet");
    setError("");
  }
  // Queue writes so an older keystroke cannot arrive after a newer answer.
  const saveRef = useRef<() => Promise<void>>(async () => {});
  async function save() {
    const currentRevision = revision.current;
    const payload: Answer = {
      selected_option_ids: draft.selected_option_ids,
      boolean_answer: draft.boolean_answer,
      free_response: draft.free_response?.trim() || null,
    };
    setStatus("Saving…");
    const pending = queue.current
      .catch(() => {})
      .then(() => quizzesApi.save(initial.id, item.id, payload));
    queue.current = pending;
    try {
      await pending;
      if (revision.current === currentRevision) {
        setDirty(false);
        setStatus("Saved");
        setError("");
        setItems((old) =>
          old.map((q) => (q.id === item.id ? { ...q, ...payload } : q)),
        );
      }
    } catch (e) {
      setStatus("Not saved");
      setError((e as Error).message);
      throw e;
    }
  }
  useEffect(() => {
    saveRef.current = save;
  });
  useEffect(() => {
    if (!dirty) return;
    const timer = setTimeout(() => {
      void saveRef.current().catch(() => {});
    }, 600);
    return () => clearTimeout(timer);
  }, [draft, dirty]);
  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  useEffect(() => {
    if (!dirty && !busy) return;
    // Save before sidebar/role links unmount this page and cancel its debounce.
    const leave = (event: MouseEvent) => {
      const link = (event.target as Element | null)?.closest<HTMLAnchorElement>(
        "a[href]",
      );
      if (
        !link ||
        link.origin !== window.location.origin ||
        event.ctrlKey ||
        event.metaKey ||
        event.shiftKey ||
        event.button !== 0
      )
        return;
      event.preventDefault();
      event.stopPropagation();
      if (busy) return;
      setBusy(true);
      void saveRef
        .current()
        .then(() => router.push(link.pathname + link.search + link.hash))
        .catch(() => setBusy(false));
    };
    document.addEventListener("click", leave, true);
    return () => document.removeEventListener("click", leave, true);
  }, [dirty, busy, router]);
  async function navigate(next: number) {
    setBusy(true);
    try {
      await save();
      if (next === index) return;
      setIndex(next);
      setDraft(items[next]);
      setDirty(false);
      setStatus("Saved");
    } catch {
    } finally {
      setBusy(false);
    }
  }
  async function finish() {
    setBusy(true);
    try {
      await save();
      dialog.current?.showModal();
      continueButton.current?.focus();
    } catch {
    } finally {
      setBusy(false);
    }
  }
  async function submit() {
    setBusy(true);
    setError("");
    try {
      await quizzesApi.submit(initial.id);
      router.replace(`/student/quizzes/attempts/${initial.id}/results`);
    } catch (e) {
      setError((e as Error).message);
      dialog.current?.close();
      setBusy(false);
    }
  }
  const currentItems = items.map((q) =>
    q.id === item.id ? { ...q, ...draft } : q,
  );
  const unanswered = currentItems.filter((q) => !isAnswered(q)).length;
  return (
    <>
      <PageHeading
        eyebrow="QUIZ IN PROGRESS"
        title={initial.quiz_title}
        description="Your answers are saved as you work. Correct answers and solutions appear only after you finish the whole quiz."
      />
      <nav aria-label="Question navigator" className="quiz-navigator">
        {currentItems.map((q, i) => (
          <button
            key={q.id}
            disabled={busy}
            className={`button ${i === index ? "button-primary" : "button-secondary"}`}
            aria-current={i === index ? "step" : undefined}
            aria-label={`Question ${i + 1}, ${isAnswered(q) ? "answered" : "unanswered"}`}
            onClick={() => void navigate(i)}
          >
            {i + 1} · {isAnswered(q) ? "Answered" : "Unanswered"}
          </button>
        ))}
      </nav>
      <article className="panel quiz-panel">
        <p>
          Question {index + 1} of {items.length} ·{" "}
          {item.response_type === "FREE_RESPONSE"
            ? "Written response · not automatically graded"
            : `${item.points} objective point${item.points === 1 ? "" : "s"}`}
        </p>
        <h2 className="quiz-question">{item.question_text}</h2>
        <fieldset disabled={busy}>
          <legend className="sr-only">Your answer</legend>
          <AnswerEditor item={item} value={draft} onChange={change} />
          <button
            className="button button-quiet"
            onClick={() => change({ ...emptyAnswer })}
          >
            Clear answer
          </button>
        </fieldset>
        <p role="status" aria-live="polite">
          {status}
        </p>
        {error && (
          <p role="alert" className="error-message">
            {error}
          </p>
        )}
        <div className="quiz-actions">
          <button
            className="button button-secondary"
            disabled={busy || index === 0}
            onClick={() => void navigate(index - 1)}
          >
            Previous question
          </button>
          <button
            className="button button-secondary"
            disabled={busy}
            onClick={() => {
              setBusy(true);
              void save()
                .catch(() => {})
                .finally(() => setBusy(false));
            }}
          >
            Save answer
          </button>
          {index < items.length - 1 && (
            <button
              className="button button-primary"
              disabled={busy}
              onClick={() => void navigate(index + 1)}
            >
              Next question
            </button>
          )}
        </div>
      </article>
      <div className="quiz-actions">
        <Link
          href="/student/quizzes"
          onClick={(e) => {
            if (dirty || busy) e.preventDefault();
          }}
          className="button button-secondary"
          aria-disabled={dirty || busy}
        >
          Back to quizzes
        </Link>
        <button
          className="button button-primary"
          disabled={busy}
          onClick={() => void finish()}
        >
          Finish Quiz
        </button>
      </div>
      <dialog
        ref={dialog}
        className="delete-dialog"
        aria-labelledby="finish-title"
        onCancel={(e) => {
          if (busy) e.preventDefault();
        }}
      >
        <h2 id="finish-title">Finish this quiz?</h2>
        <p>
          {unanswered
            ? `You have ${unanswered} unanswered question${unanswered === 1 ? "" : "s"}.`
            : "You have answered every question."}{" "}
          You cannot change your answers after submission.
        </p>
        <div className="dialog-actions">
          <button
            ref={continueButton}
            disabled={busy}
            className="button button-secondary"
            onClick={() => dialog.current?.close()}
          >
            Continue Quiz
          </button>
          <button
            disabled={busy}
            className="button button-primary"
            onClick={() => void submit()}
          >
            {busy
              ? "Submitting…"
              : unanswered
                ? "Finish Anyway"
                : "Submit Quiz"}
          </button>
        </div>
      </dialog>
    </>
  );
}
function AnswerEditor({
  item,
  value,
  onChange,
}: {
  item: AttemptItem;
  value: Answer;
  onChange: (a: Answer) => void;
}) {
  if (item.response_type === "FREE_RESPONSE")
    return (
      <MathAnswerInput
        key={item.id}
        profile={mathProfileForTopic(item.topic_slug)}
        value={value.free_response ?? ""}
        onChange={(text) => onChange({ ...emptyAnswer, free_response: text })}
      />
    );
  if (item.response_type === "TRUE_FALSE")
    return (
      <div className="quiz-options">
        {[true, false].map((b) => (
          <label key={String(b)}>
            <input
              type="radio"
              name={`answer-${item.id}`}
              checked={value.boolean_answer === b}
              onChange={() => onChange({ ...emptyAnswer, boolean_answer: b })}
            />
            {b ? "True" : "False"}
          </label>
        ))}
      </div>
    );
  const multiple = item.response_type === "MULTIPLE_SELECT";
  return (
    <div className="quiz-options">
      <p>{multiple ? "Select all that apply." : "Select one answer."}</p>
      {item.options.map((o) => (
        <label key={o.id}>
          <input
            type={multiple ? "checkbox" : "radio"}
            name={`answer-${item.id}`}
            checked={value.selected_option_ids.includes(o.id)}
            onChange={() =>
              onChange({
                ...emptyAnswer,
                selected_option_ids: multiple
                  ? value.selected_option_ids.includes(o.id)
                    ? value.selected_option_ids.filter((id) => id !== o.id)
                    : [...value.selected_option_ids, o.id]
                  : [o.id],
              })
            }
          />
          {o.text}
        </label>
      ))}
    </div>
  );
}

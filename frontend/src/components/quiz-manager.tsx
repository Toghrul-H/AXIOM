"use client";
import { useEffect, useState } from "react";
import { quizRequest, StaffQuiz, QuizEntry } from "@/lib/quizzes";
import { questionsApi, Question } from "@/lib/questions";
import { PageHeading } from "./page-heading";
import { orderedTopics } from "@/lib/use-metadata";
import { ChevronDown } from "lucide-react";
export function QuizManager() {
  const [quizzes, setQuizzes] = useState<StaffQuiz[]>([]);
  const [editing, setEditing] = useState<number | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState<StaffQuiz["status"]>("DRAFT");
  const [entries, setEntries] = useState<QuizEntry[]>([]);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [quizOffset, setQuizOffset] = useState(0);
  useEffect(() => {
    let live = true;
    quizRequest<StaffQuiz[]>(`/quizzes?limit=20&offset=${quizOffset}`)
      .then((q) => {
        if (live) setQuizzes(q);
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [quizOffset]);
  useEffect(() => {
    const abort = new AbortController();
    questionsApi
      .list(offset, 20, abort.signal, { q: search })
      .then((p) => {
        setQuestions(p.items);
        setTotal(p.total);
      })
      .catch((e) => {
        if (!abort.signal.aborted) setError(e.message);
      });
    return () => abort.abort();
  }, [offset, search]);
  function edit(q?: StaffQuiz) {
    setEditing(q?.id ?? null);
    setTitle(q?.title ?? "");
    setDescription(q?.description ?? "");
    setStatus(q?.status ?? "DRAFT");
    setEntries(q?.questions ?? []);
    setError("");
    setNotice("");
  }
  function move(i: number, delta: number) {
    const copy = [...entries];
    [copy[i], copy[i + delta]] = [copy[i + delta], copy[i]];
    setEntries(copy);
  }
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const q = await quizRequest<StaffQuiz>(
        `/quizzes${editing ? `/${editing}` : ""}`,
        editing ? "PUT" : "POST",
        {
          title,
          description: description.trim() || null,
          status,
          questions: entries.map((x) => ({
            question_id: x.question_id,
            points: x.points,
          })),
        },
      );
      edit(q);
      setQuizzes(
        await quizRequest<StaffQuiz[]>(
          `/quizzes?limit=20&offset=${quizOffset}`,
        ),
      );
      setNotice("Quiz saved. Existing attempts keep their original snapshots.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const topicMap = new Map(questions.map((q) => [q.topic.id, q.topic]));
  const groups = orderedTopics([...topicMap.values()]).map(
    ({ topic, label }) => ({
      topic,
      label,
      items: questions.filter((q) => q.topic.id === topic.id),
    }),
  );
  return (
    <>
      <PageHeading
        eyebrow="TEACHING RESOURCES"
        title="Quiz management"
        description="Compose a simple quiz from the Question Bank. Existing attempts keep the content they started with."
      />
      {error && (
        <p role="alert" className="error-message">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      <section className="panel quiz-panel quiz-management-list">
        <h2>Quizzes</h2>
        <div className="quiz-actions">
          {quizzes.map((q) => (
            <button
              disabled={busy}
              className="button button-secondary"
              key={q.id}
              onClick={() => edit(q)}
            >
              {q.title} · {q.status}
            </button>
          ))}
          <button
            disabled={busy}
            className="button button-primary"
            onClick={() => edit()}
          >
            New quiz
          </button>
        </div>
        <div className="quiz-actions">
          <button
            className="button button-quiet"
            disabled={quizOffset === 0 || busy}
            onClick={() => setQuizOffset(quizOffset - 20)}
          >
            Previous quizzes
          </button>
          <button
            className="button button-quiet"
            disabled={quizzes.length < 20 || busy}
            onClick={() => setQuizOffset(quizOffset + 20)}
          >
            More quizzes
          </button>
        </div>
      </section>
      <form onSubmit={save} className="panel quiz-panel quiz-editor">
        <h2>{editing ? "Edit quiz" : "Create quiz"}</h2>
        <fieldset disabled={busy}>
          <legend className="sr-only">Quiz composition</legend>
          <div className="field">
            <label htmlFor="quiz-title">Quiz title</label>
            <input
              id="quiz-title"
              required
              maxLength={200}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="quiz-description">Description</label>
            <textarea
              id="quiz-description"
              maxLength={20000}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="quiz-status">Availability</label>
            <select
              id="quiz-status"
              value={status}
              onChange={(e) => setStatus(e.target.value as StaffQuiz["status"])}
            >
              <option value="DRAFT">Draft</option>
              <option value="ACTIVE">Active</option>
              <option value="INACTIVE">Inactive</option>
            </select>
          </div>
          <h3>Questions in display order</h3>
          <p>
            Written-question points are excluded from automatically graded
            totals. Active quizzes require active questions.
          </p>
          <ol className="quiz-composition">
            {entries.map((entry, i) => (
              <li key={entry.question_id}>
                <span>
                  Question #{entry.question_id}{" "}
                  {questions.find((q) => q.id === entry.question_id)?.title ??
                    ""}
                </span>
                <label>
                  Points{" "}
                  <input
                    aria-label={`Points for question ${entry.question_id}`}
                    type="number"
                    min={1}
                    max={1000}
                    required
                    value={entry.points}
                    onChange={(e) =>
                      setEntries(
                        entries.map((x, j) =>
                          j === i
                            ? { ...x, points: Number(e.target.value) }
                            : x,
                        ),
                      )
                    }
                  />
                </label>
                <button
                  type="button"
                  disabled={i === 0}
                  className="button button-quiet"
                  onClick={() => move(i, -1)}
                  aria-label={`Move question ${entry.question_id} up`}
                >
                  Up
                </button>
                <button
                  type="button"
                  disabled={i === entries.length - 1}
                  className="button button-quiet"
                  onClick={() => move(i, 1)}
                  aria-label={`Move question ${entry.question_id} down`}
                >
                  Down
                </button>
                <button
                  type="button"
                  className="button button-quiet"
                  onClick={() => setEntries(entries.filter((_, j) => j !== i))}
                >
                  Remove
                </button>
              </li>
            ))}
          </ol>
          <button className="button button-primary" type="submit">
            {busy ? "Saving…" : "Save quiz"}
          </button>
          <h3 className="quiz-section-title">Add from Question Bank</h3>
          <div className="field">
            <label htmlFor="quiz-search">Search bank text / title</label>
            <input
              id="quiz-search"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setOffset(0);
              }}
            />
          </div>
          <div className="quiz-bank-picker">
            <p className="field-hint">
              Topic counts reflect the matching questions on this page.
            </p>
            {questions.length === 0 && <p>No questions match this search.</p>}
            {groups.map(({ topic, items }) => (
              <details
                className="topic-accordion"
                key={`${search}:${offset}:${topic.id}`}
                open
              >
                <summary>
                  <span>
                    {topic.parent ? `${topic.parent.name} / ` : ""}
                    {topic.name}
                  </span>
                  <span className="topic-group-count">{items.length}</span>
                  <ChevronDown size={17} />
                </summary>
                <div className="quiz-topic-items">
                  {items.map((q) => (
                    <div key={q.id}>
                      <span>
                        #{q.id} · {q.title ?? q.question_text}{" "}
                        {!q.is_active ? "(inactive)" : ""}
                      </span>
                      <button
                        type="button"
                        className="button button-secondary"
                        disabled={
                          entries.some((e) => e.question_id === q.id) ||
                          entries.length >= 100
                        }
                        onClick={() =>
                          setEntries([
                            ...entries,
                            { question_id: q.id, points: 1 },
                          ])
                        }
                        aria-label={`Add question ${q.id}`}
                      >
                        Add
                      </button>
                    </div>
                  ))}
                </div>
              </details>
            ))}
          </div>
          <div className="quiz-actions">
            <button
              type="button"
              className="button button-secondary"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - 20))}
            >
              Previous bank page
            </button>
            <button
              type="button"
              className="button button-secondary"
              disabled={offset + 20 >= total}
              onClick={() => setOffset(offset + 20)}
            >
              Next bank page
            </button>
          </div>
        </fieldset>
      </form>
    </>
  );
}

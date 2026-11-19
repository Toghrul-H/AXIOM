"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  BookOpen,
  ChevronDown,
  ChevronUp,
  Plus,
  RefreshCw,
  Save,
  Trash2,
} from "lucide-react";

import { MathText } from "./math-text";
import { PageHeading } from "./page-heading";
import {
  courseApi,
  type CourseChapter,
  type CourseLesson,
  type CourseMaterial,
  type LessonWrite,
} from "@/lib/course";
import { questionsApi, type Question } from "@/lib/questions";
import { MaterialManager, PublicMaterials } from "./course-materials";
import { useAuth } from "./auth-provider";

type Props = { mode: "student" | "manager" };
const blankChapter = (position: number) => ({ title: "", slug: "", position });
const nextPosition = (items: { position: number }[]) =>
  Math.max(-1, ...items.map((item) => item.position)) + 1;
const slugify = (value: string) =>
  value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");

function Failure({ error, retry }: { error: string; retry: () => void }) {
  return (
    <section className="panel error-state" role="alert">
      <h2>Course content is unavailable</h2>
      <p>{error}</p>
      <button className="button button-quiet" onClick={retry}>
        <RefreshCw size={16} />
        Retry
      </button>
    </section>
  );
}

export function CourseWorkspace({ mode }: Props) {
  const [chapters, setChapters] = useState<CourseChapter[]>([]);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [materials, setMaterials] = useState<CourseMaterial[]>([]);
  const [selectedLesson, setSelectedLesson] = useState<CourseLesson | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let alive = true;
    async function load() {
      await Promise.resolve();
      if (!alive) return;
      setLoading(true);
      setError("");
      try {
        const [data, page, materialData] =
          mode === "manager"
            ? await Promise.all([
                courseApi.managedChapters(),
                questionsApi.list(0, 100, undefined, { is_active: "true" }),
                courseApi.managedMaterials(),
              ])
            : await courseApi
                .publishedChapters()
                .then((items) => [items, null, []] as const);
        if (!alive) return;
        setChapters(data);
        setQuestions(page?.items ?? []);
        setMaterials([...materialData]);
        setSelectedLesson(
          (current) =>
            (current &&
              data
                .flatMap((chapter) => chapter.lessons)
                .find((lesson) => lesson.id === current.id)) ??
            null,
        );
      } catch (reason) {
        if (alive)
          setError(reason instanceof Error ? reason.message : "Please retry.");
      } finally {
        if (alive) setLoading(false);
      }
    }
    void load();
    return () => {
      alive = false;
    };
  }, [mode, revision]);

  const reload = () => setRevision((value) => value + 1);
  if (loading)
    return (
      <section className="panel" role="status">
        Loading course material…
      </section>
    );
  if (error) return <Failure error={error} retry={reload} />;
  return mode === "student" ? (
    <StudentCourse
      chapters={chapters}
      selected={selectedLesson}
      select={setSelectedLesson}
    />
  ) : (
    <CourseManager
      chapters={chapters}
      questions={questions}
      materials={materials}
      reload={reload}
    />
  );
}

type StudentCourseTab = "overview" | "materials" | "practice" | "interactive";

function StudentCourseTabs({
  active,
  select,
  studentPreview = false,
}: {
  active: StudentCourseTab;
  select: (tab: StudentCourseTab) => void;
  studentPreview?: boolean;
}) {
  const tabs: { id: StudentCourseTab; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "materials", label: "Materials" },
    { id: "practice", label: "Practice" },
    { id: "interactive", label: "Interactive tools" },
  ];
  const visibleTabs = studentPreview
    ? tabs.filter((tab) => tab.id !== "practice")
    : tabs;
  return (
    <nav
      className="course-workspace-tabs"
      aria-label="Course learning sections"
    >
      {visibleTabs.map((tab) => (
        <button
          type="button"
          key={tab.id}
          className={active === tab.id ? "is-active" : ""}
          aria-current={active === tab.id ? "page" : undefined}
          onClick={() => select(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  );
}

function StudentCourse({
  chapters,
  selected,
  select,
}: {
  chapters: CourseChapter[];
  selected: CourseLesson | null;
  select: (lesson: CourseLesson | null) => void;
}) {
  const { studentView } = useAuth();
  const [activeTab, setActiveTab] = useState<StudentCourseTab>("overview");
  const materialGroups = chapters
    .flatMap((chapter) => [
      {
        id: `chapter-${chapter.id}`,
        label: chapter.title,
        materials: chapter.materials,
      },
      ...chapter.lessons.map((lesson) => ({
        id: `lesson-${lesson.id}`,
        label: `${chapter.title} · ${lesson.title}`,
        materials: lesson.materials,
      })),
    ])
    .filter((group) => group.materials.length > 0);
  const changeTab = (tab: StudentCourseTab) => {
    setActiveTab(tab);
    select(null);
  };

  if (selected)
    return (
      <main className="course-learning-workspace">
        <StudentCourseTabs
          active="overview"
          select={changeTab}
          studentPreview={studentView}
        />
        <section className="course-layout">
          <div className="course-reading panel">
            <button
              className="button button-quiet"
              onClick={() => select(null)}
            >
              ← All lessons
            </button>
            <p className="eyebrow">COURSE LESSON</p>
            <h1>{selected.title}</h1>
            <div className="course-content">
              <MathText text={selected.content} />
            </div>
            {selected.questions.length > 0 && (
              <section>
                <h2>Practice questions</h2>
                <ul className="course-question-links">
                  {selected.questions.map((item) => (
                    <li key={item.question_id}>
                      {studentView ? (
                        <span>
                          Practice question {item.position + 1} is unavailable
                          in preview.
                        </span>
                      ) : (
                        <Link href="/student/practice">
                          Practice question {item.position + 1}
                        </Link>
                      )}
                    </li>
                  ))}
                </ul>
              </section>
            )}
            <PublicMaterials
              materials={selected.materials}
              label={selected.title}
              studentPreview={studentView}
            />
          </div>
        </section>
      </main>
    );
  return (
    <main className="course-learning-workspace">
      <PageHeading
        eyebrow="DISCRETE MATHEMATICS I"
        title="Course"
        description="Published explanations, course materials, practice links, and interactive tools."
      />
      <StudentCourseTabs
        active={activeTab}
        select={changeTab}
        studentPreview={studentView}
      />
      {activeTab === "overview" &&
        (chapters.length === 0 ? (
          <section className="panel empty-state">
            <BookOpen size={28} />
            <h2>No published lessons yet</h2>
            <p>Your lecturer has not published course material yet.</p>
          </section>
        ) : (
          <section className="course-layout">
            {chapters.map((chapter) => (
              <article className="panel course-chapter" key={chapter.id}>
                <p className="eyebrow">CHAPTER {chapter.position + 1}</p>
                <h2>{chapter.title}</h2>
                {chapter.lessons.length === 0 ? (
                  <p className="muted">
                    Lessons will appear here when published.
                  </p>
                ) : (
                  <ol>
                    {chapter.lessons.map((lesson) => (
                      <li key={lesson.id}>
                        <button
                          className="course-lesson-link"
                          onClick={() => select(lesson)}
                        >
                          <strong>{lesson.title}</strong>
                          <span>Read lesson</span>
                        </button>
                      </li>
                    ))}
                  </ol>
                )}
              </article>
            ))}
          </section>
        ))}
      {activeTab === "materials" && (
        <section className="course-materials-workspace">
          <div>
            <p className="eyebrow">COURSE MATERIALS</p>
            <h2>Published learning resources</h2>
            <p className="muted">
              Only materials published with accessible course content appear
              here.
            </p>
          </div>
          {materialGroups.length ? (
            materialGroups.map((group) => (
              <article className="panel" key={group.id}>
                <PublicMaterials
                  materials={group.materials}
                  label={group.label}
                  studentPreview={studentView}
                />
              </article>
            ))
          ) : (
            <section className="panel empty-state">
              <h2>No published materials yet</h2>
              <p>
                Materials will appear here when your lecturer publishes them.
              </p>
            </section>
          )}
        </section>
      )}
      {activeTab === "practice" && (
        <section className="panel course-resource-card">
          <div>
            <p className="eyebrow">PRACTICE</p>
            <h2>Practice questions</h2>
            <p>
              Use the existing practice workspace to work through active
              questions.
            </p>
          </div>
          <Link href="/student/practice" className="button button-primary">
            Open practice
          </Link>
        </section>
      )}
      {activeTab === "interactive" && (
        <section className="panel course-resource-card">
          <div>
            <p className="eyebrow">INTERACTIVE WORKSPACE</p>
            <h2>Truth tables and finite sets</h2>
            <p>
              Build truth tables and calculate finite-set operations directly in
              your browser.
            </p>
          </div>
          <Link
            href="/student/course/visualizations"
            className="button button-primary"
          >
            Open tools
          </Link>
        </section>
      )}
    </main>
  );
}

function CourseManager({
  chapters,
  questions,
  materials,
  reload,
}: {
  chapters: CourseChapter[];
  questions: Question[];
  materials: CourseMaterial[];
  reload: () => void;
}) {
  const [chapterDraft, setChapterDraft] = useState(blankChapter(0));
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const run = async (
    action: () => Promise<unknown>,
    success: string,
    reloadOnError = false,
  ) => {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await action();
      setNotice(success);
      reload();
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Course update failed.",
      );
      if (reloadOnError) reload();
    } finally {
      setBusy(false);
    }
  };
  async function createChapter(event: FormEvent) {
    event.preventDefault();
    await run(
      () =>
        courseApi.createChapter({
          ...chapterDraft,
          slug: chapterDraft.slug || slugify(chapterDraft.title),
          position: nextPosition(chapters),
        }),
      "Chapter created.",
    );
    setChapterDraft(blankChapter(nextPosition(chapters) + 1));
  }
  async function reorder(direction: -1 | 1, chapter: CourseChapter) {
    const index = chapters.findIndex((item) => item.id === chapter.id);
    const target = index + direction;
    if (target < 0 || target >= chapters.length) return;
    const ids = chapters.map((item) => item.id);
    [ids[index], ids[target]] = [ids[target], ids[index]];
    await run(() => courseApi.reorderChapters(ids), "Chapter order saved.");
  }
  return (
    <>
      <PageHeading
        eyebrow="TEACHING RESOURCES"
        title="Course management"
        description="Create, order, and publish course chapters and lessons."
      />
      {error && (
        <div className="error-message" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <div className="success-message" role="status">
          {notice}
        </div>
      )}
      <form className="panel course-create" onSubmit={createChapter}>
        <h2>Add chapter</h2>
        <label>
          Title
          <input
            required
            value={chapterDraft.title}
            onChange={(event) =>
              setChapterDraft({ ...chapterDraft, title: event.target.value })
            }
          />
        </label>
        <label>
          Slug
          <input
            required
            value={chapterDraft.slug}
            onChange={(event) =>
              setChapterDraft({
                ...chapterDraft,
                slug: slugify(event.target.value),
              })
            }
            placeholder="sets-and-relations"
          />
        </label>
        <button className="button button-primary" disabled={busy}>
          <Plus size={16} />
          Add chapter
        </button>
      </form>
      {chapters.length === 0 ? (
        <section className="panel empty-state">
          <h2>No chapters yet</h2>
          <p>Add a draft chapter to begin building the course.</p>
        </section>
      ) : (
        <section className="course-manager-list">
          {chapters.map((chapter, index) => (
            <ChapterEditor
              key={chapter.id}
              chapter={chapter}
              questions={questions}
              materials={materials}
              busy={busy}
              onRun={run}
              moveUp={() => reorder(-1, chapter)}
              moveDown={() => reorder(1, chapter)}
              first={index === 0}
              last={index === chapters.length - 1}
            />
          ))}
        </section>
      )}
    </>
  );
}

function ChapterEditor({
  chapter,
  questions,
  materials,
  busy,
  onRun,
  moveUp,
  moveDown,
  first,
  last,
}: {
  chapter: CourseChapter;
  questions: Question[];
  materials: CourseMaterial[];
  busy: boolean;
  onRun: (
    action: () => Promise<unknown>,
    success: string,
    reloadOnError?: boolean,
  ) => Promise<void>;
  moveUp: () => void;
  moveDown: () => void;
  first: boolean;
  last: boolean;
}) {
  const [draft, setDraft] = useState({
    title: chapter.title,
    slug: chapter.slug,
    position: chapter.position,
  });
  const [lessonDraft, setLessonDraft] = useState({
    title: "",
    slug: "",
    content: "",
    questions: [] as number[],
  });
  const save = (event: FormEvent) => {
    event.preventDefault();
    void onRun(
      () => courseApi.updateChapter(chapter.id, draft),
      "Chapter saved.",
    );
  };
  const createLesson = (event: FormEvent) => {
    event.preventDefault();
    const payload: LessonWrite = {
      chapter_id: chapter.id,
      title: lessonDraft.title,
      slug: lessonDraft.slug || slugify(lessonDraft.title),
      content: lessonDraft.content,
      position: nextPosition(chapter.lessons),
      questions: lessonDraft.questions.map((question_id) => ({ question_id })),
    };
    void onRun(() => courseApi.createLesson(payload), "Lesson created.").then(
      () => setLessonDraft({ title: "", slug: "", content: "", questions: [] }),
    );
  };
  const remove = () => {
    if (window.confirm(`Delete “${chapter.title}” and its lessons?`))
      void onRun(() => courseApi.deleteChapter(chapter.id), "Chapter deleted.");
  };
  return (
    <article className="panel course-manager-chapter">
      <header>
        <div>
          <span className={`exam-status ${chapter.status}`}>
            {chapter.status}
          </span>
          <h2>{chapter.title}</h2>
        </div>
        <div className="course-order-actions">
          <button
            className="icon-button"
            onClick={moveUp}
            disabled={busy || first}
            aria-label={`Move ${chapter.title} up`}
          >
            <ChevronUp size={16} />
          </button>
          <button
            className="icon-button"
            onClick={moveDown}
            disabled={busy || last}
            aria-label={`Move ${chapter.title} down`}
          >
            <ChevronDown size={16} />
          </button>
        </div>
      </header>
      <form className="course-inline-form" onSubmit={save}>
        <label>
          Title
          <input
            required
            value={draft.title}
            onChange={(event) =>
              setDraft({ ...draft, title: event.target.value })
            }
          />
        </label>
        <label>
          Slug
          <input
            required
            value={draft.slug}
            onChange={(event) =>
              setDraft({ ...draft, slug: slugify(event.target.value) })
            }
          />
        </label>
        <button className="button button-quiet" disabled={busy}>
          <Save size={16} />
          Save
        </button>
      </form>
      <div className="course-actions">
        <button
          className="button button-quiet"
          disabled={busy}
          onClick={() =>
            void onRun(
              () =>
                courseApi.publishChapter(
                  chapter.id,
                  chapter.status !== "published",
                ),
              chapter.status === "published"
                ? "Chapter returned to draft."
                : "Chapter published.",
            )
          }
        >
          {chapter.status === "published"
            ? "Unpublish chapter"
            : "Publish chapter"}
        </button>
        <button
          className="button button-danger"
          disabled={busy}
          onClick={remove}
        >
          <Trash2 size={16} />
          Delete
        </button>
      </div>
      <MaterialManager
        parent={{
          chapterId: chapter.id,
          label: chapter.title,
          published: chapter.status === "published",
        }}
        materials={materials.filter((item) => item.chapter_id === chapter.id)}
        busy={busy}
        onRun={onRun}
      />
      <div className="course-lessons">
        {chapter.lessons.map((lesson, index) => (
          <LessonEditor
            key={lesson.id}
            lesson={lesson}
            chapter={chapter}
            questions={questions}
            materials={materials.filter((item) => item.lesson_id === lesson.id)}
            busy={busy}
            onRun={onRun}
            index={index}
          />
        ))}
      </div>
      <form className="course-lesson-form" onSubmit={createLesson}>
        <h3>Add lesson</h3>
        <label>
          Title
          <input
            required
            value={lessonDraft.title}
            onChange={(event) =>
              setLessonDraft({ ...lessonDraft, title: event.target.value })
            }
          />
        </label>
        <label>
          Slug
          <input
            required
            value={lessonDraft.slug}
            onChange={(event) =>
              setLessonDraft({
                ...lessonDraft,
                slug: slugify(event.target.value),
              })
            }
            placeholder="set-inclusion"
          />
        </label>
        <label>
          Explanation
          <textarea
            required
            value={lessonDraft.content}
            onChange={(event) =>
              setLessonDraft({ ...lessonDraft, content: event.target.value })
            }
            placeholder="Use $...$ for inline mathematics."
          />
        </label>
        <QuestionPicker
          questions={questions}
          selected={lessonDraft.questions}
          setSelected={(questions) =>
            setLessonDraft({ ...lessonDraft, questions })
          }
        />
        <button className="button button-primary" disabled={busy}>
          <Plus size={16} />
          Add lesson
        </button>
      </form>
    </article>
  );
}

function LessonEditor({
  lesson,
  chapter,
  questions,
  materials,
  busy,
  onRun,
  index,
}: {
  lesson: CourseLesson;
  chapter: CourseChapter;
  questions: Question[];
  materials: CourseMaterial[];
  busy: boolean;
  onRun: (
    action: () => Promise<unknown>,
    success: string,
    reloadOnError?: boolean,
  ) => Promise<void>;
  index: number;
}) {
  const [draft, setDraft] = useState({
    title: lesson.title,
    slug: lesson.slug,
    content: lesson.content,
    questions: lesson.questions.map((item) => item.question_id),
  });
  const save = (event: FormEvent) => {
    event.preventDefault();
    void onRun(
      () =>
        courseApi.updateLesson(lesson.id, {
          title: draft.title,
          slug: draft.slug,
          content: draft.content,
          questions: draft.questions.map((question_id) => ({ question_id })),
        }),
      "Lesson saved.",
    );
  };
  const move = (direction: -1 | 1) => {
    const ids = chapter.lessons.map((item) => item.id);
    const target = index + direction;
    if (target < 0 || target >= ids.length) return;
    [ids[index], ids[target]] = [ids[target], ids[index]];
    void onRun(
      () => courseApi.reorderLessons(chapter.id, ids),
      "Lesson order saved.",
    );
  };
  return (
    <details className="course-lesson-editor">
      <summary>
        <strong>{lesson.title}</strong>
        <span className={`exam-status ${lesson.status}`}>{lesson.status}</span>
      </summary>
      <form onSubmit={save}>
        <label>
          Title
          <input
            required
            value={draft.title}
            onChange={(event) =>
              setDraft({ ...draft, title: event.target.value })
            }
          />
        </label>
        <label>
          Slug
          <input
            required
            value={draft.slug}
            onChange={(event) =>
              setDraft({ ...draft, slug: slugify(event.target.value) })
            }
          />
        </label>
        <label>
          Explanation
          <textarea
            required
            value={draft.content}
            onChange={(event) =>
              setDraft({ ...draft, content: event.target.value })
            }
          />
        </label>
        <QuestionPicker
          questions={questions}
          selected={draft.questions}
          setSelected={(questions) => setDraft({ ...draft, questions })}
        />
        <div className="course-actions">
          <button className="button button-quiet" disabled={busy}>
            <Save size={16} />
            Save lesson
          </button>
          <button
            type="button"
            className="button button-quiet"
            disabled={busy || index === 0}
            onClick={() => move(-1)}
          >
            Move up
          </button>
          <button
            type="button"
            className="button button-quiet"
            disabled={busy || index === chapter.lessons.length - 1}
            onClick={() => move(1)}
          >
            Move down
          </button>
          <button
            type="button"
            className="button button-quiet"
            disabled={busy}
            onClick={() =>
              void onRun(
                () =>
                  courseApi.publishLesson(
                    lesson.id,
                    lesson.status !== "published",
                  ),
                lesson.status === "published"
                  ? "Lesson returned to draft."
                  : "Lesson published.",
              )
            }
          >
            {lesson.status === "published" ? "Unpublish" : "Publish"}
          </button>
          <button
            type="button"
            className="button button-danger"
            disabled={busy}
            onClick={() => {
              if (window.confirm(`Delete “${lesson.title}”?`))
                void onRun(
                  () => courseApi.deleteLesson(lesson.id),
                  "Lesson deleted.",
                );
            }}
          >
            <Trash2 size={16} />
            Delete
          </button>
        </div>
      </form>
      <MaterialManager
        parent={{
          lessonId: lesson.id,
          label: lesson.title,
          published:
            chapter.status === "published" && lesson.status === "published",
        }}
        materials={materials}
        busy={busy}
        onRun={onRun}
      />
    </details>
  );
}

function QuestionPicker({
  questions,
  selected,
  setSelected,
}: {
  questions: Question[];
  selected: number[];
  setSelected: (ids: number[]) => void;
}) {
  const active = useMemo(
    () => questions.filter((question) => question.is_active),
    [questions],
  );
  return (
    <fieldset className="course-question-picker">
      <legend>Linked active practice questions</legend>
      {active.length === 0 ? (
        <p className="muted">No active questions available.</p>
      ) : (
        active.map((question) => (
          <label key={question.id}>
            <input
              type="checkbox"
              checked={selected.includes(question.id)}
              onChange={() =>
                setSelected(
                  selected.includes(question.id)
                    ? selected.filter((id) => id !== question.id)
                    : [...selected, question.id],
                )
              }
            />
            #{question.id}{" "}
            {question.title ?? question.question_text.slice(0, 80)}
          </label>
        ))
      )}
    </fieldset>
  );
}

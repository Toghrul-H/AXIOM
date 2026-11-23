"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import {
  BookOpen,
  ClipboardCheck,
  MessageCircle,
  RotateCcw,
  ShieldCheck,
  Users,
} from "lucide-react";
import {
  demoFixtures,
  type DemoDifficulty,
  type DemoQuestionType,
  type DemoSection,
} from "@/lib/demo-fixtures";
import { DemoProvider, useDemo } from "./demo-provider";
import { GuestModeNotice } from "./guest-mode-notice";
import { Wordmark } from "./wordmark";

const studentSections: { id: DemoSection; label: string }[] = [
  { id: "dashboard", label: "Dashboard" },
  { id: "course", label: "Course" },
  { id: "quiz", label: "Quiz" },
  { id: "tasks", label: "Tasks" },
  { id: "notifications", label: "Notifications" },
  { id: "materials", label: "Materials" },
  { id: "messages", label: "Messages" },
];

function StudentNavigation() {
  const { state, setSection } = useDemo();
  return (
    <nav className="guest-student-nav" aria-label="Student demo sections">
      {studentSections.map((item) => (
        <button
          aria-current={state.activeSection === item.id ? "page" : undefined}
          className={state.activeSection === item.id ? "is-active" : ""}
          key={item.id}
          onClick={() => setSection(item.id)}
          type="button"
        >
          {item.label}
        </button>
      ))}
    </nav>
  );
}

function StudentDashboard() {
  const { state, setSection } = useDemo();
  const baseLessonCount = demoFixtures.course.chapters.reduce(
    (total, chapter) => total + chapter.lessons.length,
    0,
  );
  const publishedAssessments = state.assessments.filter(
    (item) => item.published,
  );
  const unread = state.notifications.filter((item) => !item.read).length;
  return (
    <section className="guest-stack">
      <section className="guest-hero panel">
        <p className="eyebrow">STUDENT DEMO</p>
        <h1>Welcome to AXIOM</h1>
        <p>
          Explore a complete sample learning workflow with original content.
        </p>
      </section>
      <section className="guest-metrics">
        <button
          className="panel"
          onClick={() => setSection("course")}
          type="button"
        >
          <strong>
            {state.completedLessonIds.length}/
            {baseLessonCount +
              state.lessons.filter((item) => item.published).length}
          </strong>
          <span>Lessons complete</span>
        </button>
        <button
          className="panel"
          onClick={() => setSection("quiz")}
          type="button"
        >
          <strong>{demoFixtures.quiz.questions.length}</strong>
          <span>Quiz questions</span>
        </button>
        <button
          className="panel"
          onClick={() => setSection("tasks")}
          type="button"
        >
          <strong>
            {state.tasks.filter((task) => !task.completed).length}
          </strong>
          <span>Open tasks</span>
        </button>
        <button
          className="panel"
          onClick={() => setSection("notifications")}
          type="button"
        >
          <strong>{unread}</strong>
          <span>Unread notices</span>
        </button>
      </section>
      <section className="guest-grid">
        <article className="panel">
          <BookOpen aria-hidden="true" />
          <h2>Demo course</h2>
          <p>{demoFixtures.course.title}</p>
          <button
            className="button button-primary"
            onClick={() => setSection("course")}
            type="button"
          >
            Continue learning
          </button>
        </article>
        <article className="panel">
          <ClipboardCheck aria-hidden="true" />
          <h2>Available demo assessments</h2>
          <p>
            {publishedAssessments.length
              ? publishedAssessments.map((item) => item.title).join(" · ")
              : "No sample assessment is published."}
          </p>
          <button
            className="button button-secondary"
            onClick={() => setSection("quiz")}
            type="button"
          >
            Open sample quiz
          </button>
        </article>
      </section>
      <section className="panel">
        <MessageCircle aria-hidden="true" />
        <h2>Study Partner sample</h2>
        <p>
          <strong>{state.messages[0]?.author}:</strong>{" "}
          {state.messages[0]?.text}
        </p>
        <button
          className="button button-quiet"
          onClick={() => setSection("messages")}
          type="button"
        >
          Open demo messages
        </button>
        <p className="field-hint">
          Guest Mode never loads real profiles or conversations.
        </p>
      </section>
    </section>
  );
}

function LessonList({
  lessons,
  completed,
  onComplete,
}: {
  lessons: { id: string; title: string; content: string }[];
  completed: string[];
  onComplete: (id: string) => void;
}) {
  return (
    <div className="guest-lessons">
      {lessons.map((lesson) => {
        const complete = completed.includes(lesson.id);
        return (
          <section key={lesson.id}>
            <h3>{lesson.title}</h3>
            <p>{lesson.content}</p>
            <button
              className="button button-quiet"
              disabled={complete}
              onClick={() => onComplete(lesson.id)}
              type="button"
            >
              {complete ? "Completed" : "Mark lesson complete"}
            </button>
          </section>
        );
      })}
    </div>
  );
}
function CourseDemo() {
  const { state, completeLesson } = useDemo();
  return (
    <section className="guest-stack">
      <section className="panel">
        <p className="eyebrow">COURSE DEMO</p>
        <h1>{demoFixtures.course.title}</h1>
        <p>
          Original sample explanations; progress is temporary for this browser
          session.
        </p>
      </section>
      {demoFixtures.course.chapters.map((chapter) => (
        <article className="panel" key={chapter.id}>
          <h2>{chapter.title}</h2>
          <LessonList
            lessons={chapter.lessons}
            completed={state.completedLessonIds}
            onComplete={completeLesson}
          />
        </article>
      ))}
      {state.lessons.filter((lesson) => lesson.published).length > 0 && (
        <article className="panel">
          <h2>Lecturer-published demo lessons</h2>
          <LessonList
            lessons={state.lessons.filter((lesson) => lesson.published)}
            completed={state.completedLessonIds}
            onComplete={completeLesson}
          />
        </article>
      )}
    </section>
  );
}

function QuizDemo() {
  const { state, chooseQuizAnswer, moveQuiz, retakeQuiz, submitQuiz } =
    useDemo();
  const questions = demoFixtures.quiz.questions;
  const question = questions[state.quizIndex];
  const score = questions.reduce(
    (total, item) =>
      total + Number(state.quizAnswers[item.id] === item.correctIndex),
    0,
  );
  if (state.quizSubmitted)
    return (
      <section className="guest-stack">
        <section className="panel">
          <p className="eyebrow">QUIZ REVIEW</p>
          <h1>{demoFixtures.quiz.title}</h1>
          <p className="guest-score">
            {score} / {questions.length}
          </p>
          <p>Automatically graded from your temporary demo answers.</p>
          <button
            className="button button-primary"
            onClick={retakeQuiz}
            type="button"
          >
            Retake quiz
          </button>
        </section>
        {questions.map((item, index) => (
          <article className="panel" key={item.id}>
            <h2>
              {index + 1}. {item.prompt}
            </h2>
            <p
              className={
                state.quizAnswers[item.id] === item.correctIndex
                  ? "guest-correct"
                  : "guest-incorrect"
              }
            >
              {state.quizAnswers[item.id] === item.correctIndex
                ? "Correct"
                : "Review the explanation"}
            </p>
            <p>
              <strong>Answer:</strong> {item.options[item.correctIndex]}
            </p>
            <p className="muted">{item.explanation}</p>
          </article>
        ))}
      </section>
    );
  return (
    <section className="guest-stack">
      <section className="panel guest-quiz">
        <p className="eyebrow">
          SAMPLE QUIZ · QUESTION {state.quizIndex + 1} OF {questions.length}
        </p>
        <h1>{demoFixtures.quiz.title}</h1>
        <h2>{question.prompt}</h2>
        <fieldset>
          <legend className="sr-only">Select an answer</legend>
          {question.options.map((option, index) => (
            <label className="guest-quiz-option" key={option}>
              <input
                checked={state.quizAnswers[question.id] === index}
                name={question.id}
                onChange={() => chooseQuizAnswer(question.id, index)}
                type="radio"
              />{" "}
              {option}
            </label>
          ))}
        </fieldset>
        <div className="guest-actions">
          <button
            className="button button-quiet"
            disabled={state.quizIndex === 0}
            onClick={() => moveQuiz(-1)}
            type="button"
          >
            Previous
          </button>
          {state.quizIndex === questions.length - 1 ? (
            <button
              className="button button-primary"
              onClick={submitQuiz}
              type="button"
            >
              Submit demo quiz
            </button>
          ) : (
            <button
              className="button button-primary"
              onClick={() => moveQuiz(1)}
              type="button"
            >
              Next
            </button>
          )}
        </div>
        <p className="field-hint">
          Answers remain local; no assessment attempt is created.
        </p>
      </section>
    </section>
  );
}

function TasksDemo() {
  const { state, deleteTask, saveTask, toggleTask } = useDemo();
  const [draft, setDraft] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    saveTask(editing, draft);
    setDraft("");
    setEditing(null);
  };
  return (
    <section className="guest-stack">
      <section className="panel">
        <p className="eyebrow">PERSONAL TASKS</p>
        <h1>Plan your study time</h1>
        <form className="guest-task-form" onSubmit={submit}>
          <label className="sr-only" htmlFor="demo-task">
            Task
          </label>
          <input
            id="demo-task"
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Add a sample task"
            required
            value={draft}
          />
          <button className="button button-primary">
            {editing ? "Save task" : "Add task"}
          </button>
          {editing && (
            <button
              className="button button-quiet"
              onClick={() => {
                setEditing(null);
                setDraft("");
              }}
              type="button"
            >
              Cancel
            </button>
          )}
        </form>
        <ul className="guest-list">
          {state.tasks.map((task) => (
            <li key={task.id}>
              <label>
                <input
                  checked={task.completed}
                  onChange={() => toggleTask(task.id)}
                  type="checkbox"
                />{" "}
                <span className={task.completed ? "is-complete" : ""}>
                  {task.title}
                </span>
              </label>
              <span>
                <button
                  className="button button-quiet"
                  onClick={() => {
                    setEditing(task.id);
                    setDraft(task.title);
                  }}
                  type="button"
                >
                  Edit
                </button>
                <button
                  className="button button-quiet"
                  onClick={() => deleteTask(task.id)}
                  type="button"
                >
                  Delete
                </button>
              </span>
            </li>
          ))}
        </ul>
      </section>
    </section>
  );
}
function NotificationsDemo() {
  const { markAllNotificationsRead, openNotification, state } = useDemo();
  return (
    <section className="guest-stack">
      <section className="panel">
        <p className="eyebrow">NOTIFICATIONS</p>
        <h1>Sample updates</h1>
        <button
          className="button button-secondary"
          onClick={markAllNotificationsRead}
          type="button"
        >
          Mark all read
        </button>
        <ul className="guest-list">
          {state.notifications.map((notice) => (
            <li className={notice.read ? "" : "is-unread"} key={notice.id}>
              <span>{notice.title}</span>
              <button
                className="button button-quiet"
                onClick={() => openNotification(notice.id)}
                type="button"
              >
                Open
              </button>
            </li>
          ))}
        </ul>
      </section>
    </section>
  );
}
function MaterialsDemo() {
  const [selected, setSelected] = useState<string | null>(null);
  return (
    <section className="guest-stack">
      <section className="panel">
        <p className="eyebrow">COURSE MATERIALS</p>
        <h1>Original sample resources</h1>
        <ul className="guest-list">
          {demoFixtures.materials.map((material) => (
            <li key={material}>
              <span>{material}</span>
              <button
                className="button button-quiet"
                onClick={() => setSelected(material)}
                type="button"
              >
                View sample
              </button>
            </li>
          ))}
        </ul>
        {selected && (
          <SampleDocumentPreview title={selected} variant="material" />
        )}
        <p className="field-hint">
          University Content — Restricted Access. Real course materials are
          available only to authorized ELTE users. These are local sample
          previews, not university files or downloads.
        </p>
      </section>
    </section>
  );
}

function SampleDocumentPreview({
  title,
  variant,
}: {
  title: string;
  variant: "material" | "assessment";
}) {
  return (
    <article className="guest-material-preview" aria-live="polite">
      <p className="eyebrow">SAMPLE DOCUMENT PREVIEW</p>
      <h3>{title}</h3>
      {variant === "material" ? (
        <p>
          Use logical notation consistently, define sets before manipulating
          them, and check each conclusion against its assumptions.
        </p>
      ) : (
        <>
          <p>
            <strong>1.</strong> Let A = &#123;1, 2&#125; and B = &#123;2,
            3&#125;. Find A ∩ B and briefly justify your answer.
          </p>
          <p>
            <strong>2.</strong> State the contrapositive of p → q.
          </p>
        </>
      )}
      <p className="field-hint">
        This is an original in-browser sample document preview. No PDF has been
        generated, downloaded, or requested from AXIOM services.
      </p>
    </article>
  );
}
function MessagesDemo() {
  const { sendDemoMessage, state } = useDemo();
  const [draft, setDraft] = useState("");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    sendDemoMessage(draft);
    setDraft("");
  };
  return (
    <section className="guest-stack">
      <section className="panel">
        <p className="eyebrow">STUDY PARTNER DEMO</p>
        <h1>Sample conversation</h1>
        <div className="guest-message-list" aria-live="polite">
          {state.messages.map((message) => (
            <article className={message.mine ? "mine" : ""} key={message.id}>
              <strong>{message.author}</strong>
              <p>{message.text}</p>
            </article>
          ))}
        </div>
        <form className="guest-task-form" onSubmit={submit}>
          <label className="sr-only" htmlFor="demo-message">
            Message
          </label>
          <input
            id="demo-message"
            maxLength={500}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Write a demo message"
            required
            value={draft}
          />
          <button className="button button-primary">Send</button>
        </form>
        <p className="field-hint">
          Messages and replies are synthetic and remain only in this Guest Mode
          session.
        </p>
      </section>
    </section>
  );
}
function StudentDemo() {
  const { state } = useDemo();
  const content: Record<DemoSection, React.ReactNode> = {
    dashboard: <StudentDashboard />,
    course: <CourseDemo />,
    quiz: <QuizDemo />,
    tasks: <TasksDemo />,
    notifications: <NotificationsDemo />,
    materials: <MaterialsDemo />,
    messages: <MessagesDemo />,
  };
  return (
    <main className="guest-content">
      <StudentNavigation />
      {content[state.activeSection]}
    </main>
  );
}

type LecturerSection =
  "dashboard" | "questions" | "assessments" | "grading" | "course" | "messages";
function LecturerDemo() {
  const [section, setSection] = useState<LecturerSection>("dashboard");
  const tabs: { id: LecturerSection; label: string }[] = [
    { id: "dashboard", label: "Dashboard" },
    { id: "questions", label: "Question Bank" },
    { id: "assessments", label: "Assessments" },
    { id: "grading", label: "Grading" },
    { id: "course", label: "Course" },
    { id: "messages", label: "Messages" },
  ];
  return (
    <main className="guest-content">
      <section className="guest-hero panel">
        <p className="eyebrow">LECTURER DEMO</p>
        <h1>Explore teaching operations</h1>
        <p>
          All questions, submissions, messages, and materials below are original
          demonstration data.
        </p>
      </section>
      <nav className="guest-demo-tabs" aria-label="Lecturer demo sections">
        {tabs.map((tab) => (
          <button
            aria-current={section === tab.id ? "page" : undefined}
            className={section === tab.id ? "is-active" : ""}
            key={tab.id}
            onClick={() => setSection(tab.id)}
            type="button"
          >
            {tab.label}
          </button>
        ))}
      </nav>
      {section === "dashboard" && <LecturerDashboard onNavigate={setSection} />}
      {section === "questions" && <QuestionBankDemo />}
      {section === "assessments" && <AssessmentDemo />}
      {section === "grading" && <GradingDemo />}
      {section === "course" && <CourseManagementDemo />}
      {section === "messages" && <MessagesDemo />}
    </main>
  );
}
function LecturerDashboard({
  onNavigate,
}: {
  onNavigate: (section: LecturerSection) => void;
}) {
  const { state } = useDemo();
  const ungraded = state.submissions.filter(
    (item) => item.status === "ungraded",
  ).length;
  return (
    <section className="guest-stack">
      <section className="guest-grid">
        <article className="panel">
          <ClipboardCheck aria-hidden="true" />
          <h2>Pending grading</h2>
          <strong className="guest-metric">{ungraded}</strong>
          <button
            className="button button-quiet"
            onClick={() => onNavigate("grading")}
            type="button"
          >
            Review submissions
          </button>
        </article>
        <article className="panel">
          <BookOpen aria-hidden="true" />
          <h2>Question Bank</h2>
          <strong className="guest-metric">{state.questions.length}</strong>
          <button
            className="button button-quiet"
            onClick={() => onNavigate("questions")}
            type="button"
          >
            Manage demo questions
          </button>
        </article>
        <article className="panel">
          <Users aria-hidden="true" />
          <h2>Published lessons</h2>
          <strong className="guest-metric">
            {state.lessons.filter((item) => item.published).length}
          </strong>
          <button
            className="button button-quiet"
            onClick={() => onNavigate("course")}
            type="button"
          >
            Manage course
          </button>
        </article>
      </section>
      <section className="panel">
        <h2>Guest Mode safeguard</h2>
        <p>
          These controls update temporary synthetic state shared with Student
          Demo. They never call AXIOM APIs or change university content.
        </p>
      </section>
    </section>
  );
}

function QuestionBankDemo() {
  const { deleteQuestion, saveQuestion, state } = useDemo();
  const [query, setQuery] = useState("");
  const [type, setType] = useState<"all" | DemoQuestionType>("all");
  const [difficulty, setDifficulty] = useState<"all" | DemoDifficulty>("all");
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState({
    title: "",
    text: "",
    type: "multiple_choice" as DemoQuestionType,
    difficulty: "easy" as DemoDifficulty,
  });
  const filtered = state.questions.filter(
    (item) =>
      (type === "all" || item.type === type) &&
      (difficulty === "all" || item.difficulty === difficulty) &&
      `${item.title} ${item.text}`.toLowerCase().includes(query.toLowerCase()),
  );
  const submit = (event: FormEvent) => {
    event.preventDefault();
    saveQuestion(editing, draft);
    setEditing(null);
    setDraft({
      title: "",
      text: "",
      type: "multiple_choice",
      difficulty: "easy",
    });
  };
  return (
    <section className="guest-stack">
      <section className="panel">
        <h2>Question Bank</h2>
        <p className="field-hint">
          Search, filter, and manage original demo questions without contacting
          the real question bank.
        </p>
        <div className="guest-manager-grid">
          <input
            aria-label="Search demo questions"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search questions"
            value={query}
          />
          <select
            aria-label="Question type"
            onChange={(event) =>
              setType(event.target.value as "all" | DemoQuestionType)
            }
            value={type}
          >
            <option value="all">All types</option>
            <option value="multiple_choice">Multiple choice</option>
            <option value="true_false">True/false</option>
            <option value="free_response">Free response</option>
          </select>
          <select
            aria-label="Question difficulty"
            onChange={(event) =>
              setDifficulty(event.target.value as "all" | DemoDifficulty)
            }
            value={difficulty}
          >
            <option value="all">All difficulties</option>
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </select>
        </div>
        <form className="guest-manager-grid" onSubmit={submit}>
          <input
            aria-label="Question title"
            onChange={(event) =>
              setDraft({ ...draft, title: event.target.value })
            }
            placeholder="Question title"
            required
            value={draft.title}
          />
          <textarea
            aria-label="Question text"
            onChange={(event) =>
              setDraft({ ...draft, text: event.target.value })
            }
            placeholder="Original mathematical question text"
            required
            value={draft.text}
          />
          <select
            aria-label="New question type"
            onChange={(event) =>
              setDraft({
                ...draft,
                type: event.target.value as DemoQuestionType,
              })
            }
            value={draft.type}
          >
            <option value="multiple_choice">Multiple choice</option>
            <option value="true_false">True/false</option>
            <option value="free_response">Free response</option>
          </select>
          <select
            aria-label="New question difficulty"
            onChange={(event) =>
              setDraft({
                ...draft,
                difficulty: event.target.value as DemoDifficulty,
              })
            }
            value={draft.difficulty}
          >
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </select>
          <button className="button button-primary">
            {editing ? "Save question" : "Add question"}
          </button>
          {editing && (
            <button
              className="button button-quiet"
              onClick={() => {
                setEditing(null);
                setDraft({
                  title: "",
                  text: "",
                  type: "multiple_choice",
                  difficulty: "easy",
                });
              }}
              type="button"
            >
              Cancel
            </button>
          )}
        </form>
      </section>
      <section className="guest-stack">
        {filtered.map((item) => (
          <article className="panel guest-record" key={item.id}>
            <div>
              <h3>{item.title}</h3>
              <p>{item.text}</p>
              <span className="status-badge">
                {item.type.replace("_", " ")} · {item.difficulty}
              </span>
            </div>
            <div className="guest-actions">
              <button
                className="button button-quiet"
                onClick={() => {
                  setEditing(item.id);
                  setDraft({
                    title: item.title,
                    text: item.text,
                    type: item.type,
                    difficulty: item.difficulty,
                  });
                }}
                type="button"
              >
                Edit
              </button>
              <button
                className="button button-quiet"
                onClick={() => deleteQuestion(item.id)}
                type="button"
              >
                Delete
              </button>
            </div>
          </article>
        ))}
        {filtered.length === 0 && (
          <section className="panel">
            <p>No demo questions match these filters.</p>
          </section>
        )}
      </section>
    </section>
  );
}
function AssessmentDemo() {
  const {
    saveAssessment,
    setRole,
    setSection,
    state,
    toggleAssessmentPublication,
  } = useDemo();
  const [editing, setEditing] = useState<string | null>(null);
  const [previewTitle, setPreviewTitle] = useState<string | null>(null);
  const [draft, setDraft] = useState({
    title: "",
    description: "",
    questionIds: [] as string[],
    durationMinutes: 30,
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    saveAssessment(editing, draft);
    setEditing(null);
    setDraft({
      title: "",
      description: "",
      questionIds: [],
      durationMinutes: 30,
    });
  };
  return (
    <section className="guest-stack">
      <section className="panel">
        <h2>Assessments</h2>
        <form className="guest-manager-grid" onSubmit={submit}>
          <input
            aria-label="Assessment title"
            onChange={(event) =>
              setDraft({ ...draft, title: event.target.value })
            }
            placeholder="Assessment title"
            required
            value={draft.title}
          />
          <textarea
            aria-label="Assessment description"
            onChange={(event) =>
              setDraft({ ...draft, description: event.target.value })
            }
            placeholder="Original description"
            value={draft.description}
          />
          <input
            aria-label="Duration in minutes"
            min="1"
            onChange={(event) =>
              setDraft({
                ...draft,
                durationMinutes: Number(event.target.value) || 1,
              })
            }
            type="number"
            value={draft.durationMinutes}
          />
          <fieldset>
            <legend>Include demo questions</legend>
            {state.questions.map((question) => (
              <label key={question.id}>
                <input
                  checked={draft.questionIds.includes(question.id)}
                  onChange={() =>
                    setDraft({
                      ...draft,
                      questionIds: draft.questionIds.includes(question.id)
                        ? draft.questionIds.filter((id) => id !== question.id)
                        : [...draft.questionIds, question.id],
                    })
                  }
                  type="checkbox"
                />{" "}
                {question.title}
              </label>
            ))}
          </fieldset>
          <button className="button button-primary">
            {editing ? "Save assessment" : "Create assessment"}
          </button>
          {editing && (
            <button
              className="button button-quiet"
              onClick={() => {
                setEditing(null);
                setDraft({
                  title: "",
                  description: "",
                  questionIds: [],
                  durationMinutes: 30,
                });
              }}
              type="button"
            >
              Cancel
            </button>
          )}
        </form>
      </section>
      {state.assessments.map((assessment) => (
        <article className="panel guest-record" key={assessment.id}>
          <div>
            <h3>{assessment.title}</h3>
            <p>{assessment.description || "No description provided."}</p>
            <p className="field-hint">
              {assessment.questionIds.length} demo question(s) ·{" "}
              {assessment.durationMinutes} minutes
            </p>
            <span className="status-badge">
              {assessment.published ? "Published in Student Demo" : "Draft"}
            </span>
          </div>
          <div className="guest-actions">
            <button
              className="button button-secondary"
              onClick={() => toggleAssessmentPublication(assessment.id)}
              type="button"
            >
              {assessment.published ? "Unpublish" : "Publish"}
            </button>
            <button
              className="button button-quiet"
              onClick={() => {
                setEditing(assessment.id);
                setDraft({
                  title: assessment.title,
                  description: assessment.description,
                  questionIds: assessment.questionIds,
                  durationMinutes: assessment.durationMinutes,
                });
              }}
              type="button"
            >
              Edit
            </button>
            <button
              className="button button-quiet"
              onClick={() => setPreviewTitle(assessment.title)}
              type="button"
            >
              Preview sample document
            </button>
            {assessment.published && (
              <button
                className="button button-quiet"
                onClick={() => {
                  setRole("student");
                  setSection("dashboard");
                }}
                type="button"
              >
                Preview as student
              </button>
            )}
          </div>
        </article>
      ))}
      {previewTitle && (
        <SampleDocumentPreview title={previewTitle} variant="assessment" />
      )}
    </section>
  );
}
function GradingDemo() {
  const { gradeSubmission, state } = useDemo();
  const [drafts, setDrafts] = useState<
    Record<string, { score: string; feedback: string }>
  >({});
  return (
    <section className="guest-stack">
      <section className="panel">
        <h2>Grading queue</h2>
        <p className="field-hint">
          Exactly two original sample submissions start ungraded after Reset
          Demo.
        </p>
      </section>
      {state.submissions.map((item) => {
        const draft = drafts[item.id] ?? { score: "10", feedback: "" };
        return (
          <article className="panel" key={item.id}>
            <strong>{item.studentLabel}</strong>
            <h3>{item.question}</h3>
            <p className="muted">“{item.response}”</p>
            <p>
              <strong>Criteria:</strong> {item.criteria}
            </p>
            {item.status === "ungraded" ? (
              <div className="guest-manager-grid">
                <input
                  aria-label={`Score for ${item.studentLabel}`}
                  max="10"
                  min="0"
                  onChange={(event) =>
                    setDrafts({
                      ...drafts,
                      [item.id]: { ...draft, score: event.target.value },
                    })
                  }
                  type="number"
                  value={draft.score}
                />
                <textarea
                  aria-label={`Feedback for ${item.studentLabel}`}
                  onChange={(event) =>
                    setDrafts({
                      ...drafts,
                      [item.id]: { ...draft, feedback: event.target.value },
                    })
                  }
                  placeholder="Optional sample feedback"
                  value={draft.feedback}
                />
                <button
                  className="button button-primary"
                  onClick={() =>
                    gradeSubmission(
                      item.id,
                      Number(draft.score),
                      draft.feedback,
                    )
                  }
                  type="button"
                >
                  Complete demo review
                </button>
              </div>
            ) : (
              <section>
                <span className="status-badge">Reviewed · {item.score}/10</span>
                {item.feedback && (
                  <p>
                    <strong>Feedback:</strong> {item.feedback}
                  </p>
                )}
              </section>
            )}
          </article>
        );
      })}
    </section>
  );
}
function CourseManagementDemo() {
  const { saveLesson, state, toggleLessonPublication } = useDemo();
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState({ title: "", content: "" });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    saveLesson(editing, draft);
    setEditing(null);
    setDraft({ title: "", content: "" });
  };
  return (
    <section className="guest-stack">
      <section className="panel">
        <h2>Course publication</h2>
        <form className="guest-manager-grid" onSubmit={submit}>
          <input
            aria-label="Lesson title"
            onChange={(event) =>
              setDraft({ ...draft, title: event.target.value })
            }
            placeholder="Lesson title"
            required
            value={draft.title}
          />
          <textarea
            aria-label="Lesson explanation"
            onChange={(event) =>
              setDraft({ ...draft, content: event.target.value })
            }
            placeholder="Original explanation"
            required
            value={draft.content}
          />
          <button className="button button-primary">
            {editing ? "Save lesson" : "Create lesson"}
          </button>
          {editing && (
            <button
              className="button button-quiet"
              onClick={() => {
                setEditing(null);
                setDraft({ title: "", content: "" });
              }}
              type="button"
            >
              Cancel
            </button>
          )}
        </form>
      </section>
      {state.lessons.map((lesson) => (
        <article className="panel guest-record" key={lesson.id}>
          <div>
            <h3>{lesson.title}</h3>
            <p>{lesson.content}</p>
            <span className="status-badge">
              {lesson.published ? "Visible in Student Demo" : "Draft"}
            </span>
          </div>
          <div className="guest-actions">
            <button
              className="button button-secondary"
              onClick={() => toggleLessonPublication(lesson.id)}
              type="button"
            >
              {lesson.published ? "Unpublish" : "Publish"}
            </button>
            <button
              className="button button-quiet"
              onClick={() => {
                setEditing(lesson.id);
                setDraft({ title: lesson.title, content: lesson.content });
              }}
              type="button"
            >
              Edit
            </button>
          </div>
        </article>
      ))}
    </section>
  );
}
function DemoWorkspace() {
  const { role, setRole, reset, notice } = useDemo();
  return (
    <div className="guest-mode">
      <header className="guest-header">
        <Wordmark />
        <nav aria-label="Guest Mode controls">
          <button
            aria-pressed={role === "student"}
            className="button button-quiet"
            onClick={() => setRole("student")}
            type="button"
          >
            Student Demo
          </button>
          <button
            aria-pressed={role === "lecturer"}
            className="button button-quiet"
            onClick={() => setRole("lecturer")}
            type="button"
          >
            Lecturer Demo
          </button>
          <button
            className="button button-secondary"
            onClick={reset}
            type="button"
          >
            <RotateCcw size={16} /> Reset Demo
          </button>
          <Link className="button button-quiet" href="/login">
            Exit Demo
          </Link>
        </nav>
      </header>
      <section className="guest-banner" role="status">
        <ShieldCheck aria-hidden="true" />
        <span>
          <strong>Guest Mode</strong> — You’re exploring AXIOM with sample data.
          Changes are not saved.
        </span>
      </section>
      <GuestModeNotice message={notice} />
      <section className="guest-restricted" role="note">
        <strong>University Content — Restricted Access.</strong> This material
        is available only to authorized ELTE users. Explore the demonstration
        using original sample content.
      </section>
      {role === "student" ? <StudentDemo /> : <LecturerDemo />}
    </div>
  );
}
export function GuestMode() {
  return (
    <DemoProvider>
      <DemoWorkspace />
    </DemoProvider>
  );
}

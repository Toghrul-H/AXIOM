"use client";

import { createContext, useContext, useMemo, useState } from "react";
import {
  demoFixtures,
  type DemoRole,
  type DemoSection,
  type DemoAssessment,
  type DemoDifficulty,
  type DemoQuestionType,
  freshDemoState,
  type DemoState,
} from "@/lib/demo-fixtures";

type DemoContextValue = {
  role: DemoRole;
  state: DemoState;
  notice: string | null;
  setRole: (role: DemoRole) => void;
  setSection: (section: DemoSection) => void;
  reset: () => void;
  saveTask: (id: string | null, title: string) => void;
  deleteTask: (id: string) => void;
  toggleTask: (id: string) => void;
  markNotificationRead: (id: string) => void;
  markAllNotificationsRead: () => void;
  openNotification: (id: string) => void;
  completeLesson: (id: string) => void;
  chooseQuizAnswer: (questionId: string, option: number) => void;
  moveQuiz: (direction: -1 | 1) => void;
  submitQuiz: () => void;
  retakeQuiz: () => void;
  saveQuestion: (
    id: string | null,
    question: {
      title: string;
      text: string;
      type: DemoQuestionType;
      difficulty: DemoDifficulty;
    },
  ) => void;
  deleteQuestion: (id: string) => void;
  saveAssessment: (
    id: string | null,
    assessment: Omit<DemoAssessment, "id" | "published">,
  ) => void;
  toggleAssessmentPublication: (id: string) => void;
  saveLesson: (
    id: string | null,
    lesson: { title: string; content: string },
  ) => void;
  toggleLessonPublication: (id: string) => void;
  gradeSubmission: (id: string, score: number, feedback: string) => void;
  sendDemoMessage: (text: string) => void;
};

const DemoContext = createContext<DemoContextValue | null>(null);

export function useDemo() {
  const value = useContext(DemoContext);
  if (!value) throw new Error("Missing DemoProvider");
  return value;
}

export function DemoProvider({ children }: { children: React.ReactNode }) {
  const [role, setRole] = useState<DemoRole>("student");
  const [state, setState] = useState<DemoState>(freshDemoState);
  const [notice, setNotice] = useState<string | null>(null);
  const update = (callback: (current: DemoState) => DemoState) =>
    setState(callback);
  const value = useMemo<DemoContextValue>(
    () => ({
      role,
      state,
      notice,
      setRole: (nextRole) => {
        setRole(nextRole);
        setNotice(null);
      },
      setSection: (activeSection) =>
        update((current) => ({ ...current, activeSection })),
      reset: () => {
        setState(freshDemoState());
        setNotice("Demo reset. All sample changes were discarded.");
      },
      saveTask: (id, title) => {
        const value = title.trim();
        if (!value) return;
        update((current) => ({
          ...current,
          tasks: id
            ? current.tasks.map((task) =>
                task.id === id ? { ...task, title: value } : task,
              )
            : [
                ...current.tasks,
                { id: `task-${Date.now()}`, title: value, completed: false },
              ],
        }));
        setNotice(
          "Demo task updated. Authorized AXIOM users can save personal tasks to their account.",
        );
      },
      deleteTask: (id) => {
        update((current) => ({
          ...current,
          tasks: current.tasks.filter((task) => task.id !== id),
        }));
        setNotice("Demo task removed. Guest Mode changes are not saved.");
      },
      toggleTask: (id) =>
        update((current) => ({
          ...current,
          tasks: current.tasks.map((task) =>
            task.id === id ? { ...task, completed: !task.completed } : task,
          ),
        })),
      markNotificationRead: (id) =>
        update((current) => ({
          ...current,
          notifications: current.notifications.map((item) =>
            item.id === id ? { ...item, read: true } : item,
          ),
        })),
      markAllNotificationsRead: () =>
        update((current) => ({
          ...current,
          notifications: current.notifications.map((item) => ({
            ...item,
            read: true,
          })),
        })),
      openNotification: (id) =>
        update((current) => {
          const item = current.notifications.find((notice) => notice.id === id);
          return item
            ? {
                ...current,
                activeSection: item.target,
                notifications: current.notifications.map((notice) =>
                  notice.id === id ? { ...notice, read: true } : notice,
                ),
              }
            : current;
        }),
      completeLesson: (id) =>
        update((current) =>
          current.completedLessonIds.includes(id)
            ? current
            : {
                ...current,
                completedLessonIds: [...current.completedLessonIds, id],
              },
        ),
      chooseQuizAnswer: (questionId, option) =>
        update((current) => ({
          ...current,
          quizAnswers: { ...current.quizAnswers, [questionId]: option },
        })),
      moveQuiz: (direction) =>
        update((current) => ({
          ...current,
          quizIndex: Math.max(
            0,
            Math.min(
              demoFixtures.quiz.questions.length - 1,
              current.quizIndex + direction,
            ),
          ),
        })),
      submitQuiz: () => {
        update((current) => ({ ...current, quizSubmitted: true }));
        setNotice(
          "Demo quiz graded locally. Guest Mode never creates a real assessment attempt.",
        );
      },
      retakeQuiz: () => {
        update((current) => ({
          ...current,
          quizIndex: 0,
          quizAnswers: {},
          quizSubmitted: false,
        }));
        setNotice(
          "Demo quiz reset. Your previous sample answers were discarded.",
        );
      },
      saveQuestion: (id, question) => {
        const title = question.title.trim();
        const text = question.text.trim();
        if (!title || !text) return;
        update((current) => ({
          ...current,
          questions: id
            ? current.questions.map((item) =>
                item.id === id ? { ...item, ...question, title, text } : item,
              )
            : [
                ...current.questions,
                { ...question, id: `question-${Date.now()}`, title, text },
              ],
        }));
        setNotice(
          "Demo question saved locally. Guest Mode never changes the AXIOM Question Bank.",
        );
      },
      deleteQuestion: (id) => {
        update((current) => ({
          ...current,
          questions: current.questions.filter((item) => item.id !== id),
          assessments: current.assessments.map((assessment) => ({
            ...assessment,
            questionIds: assessment.questionIds.filter(
              (questionId) => questionId !== id,
            ),
          })),
        }));
        setNotice(
          "Demo question removed locally. Guest Mode changes reset when the demo is reset.",
        );
      },
      saveAssessment: (id, assessment) => {
        const title = assessment.title.trim();
        if (!title) return;
        update((current) => ({
          ...current,
          assessments: id
            ? current.assessments.map((item) =>
                item.id === id ? { ...item, ...assessment, title } : item,
              )
            : [
                ...current.assessments,
                {
                  ...assessment,
                  id: `assessment-${Date.now()}`,
                  title,
                  published: false,
                },
              ],
        }));
        setNotice(
          "Demo assessment saved locally. Publishing is also limited to this demo session.",
        );
      },
      toggleAssessmentPublication: (id) => {
        update((current) => ({
          ...current,
          assessments: current.assessments.map((item) =>
            item.id === id ? { ...item, published: !item.published } : item,
          ),
        }));
        setNotice(
          "Demo assessment visibility updated. No real assessment or student attempt was changed.",
        );
      },
      saveLesson: (id, lesson) => {
        const title = lesson.title.trim();
        const content = lesson.content.trim();
        if (!title || !content) return;
        update((current) => ({
          ...current,
          lessons: id
            ? current.lessons.map((item) =>
                item.id === id ? { ...item, title, content } : item,
              )
            : [
                ...current.lessons,
                {
                  id: `lesson-${Date.now()}`,
                  title,
                  content,
                  published: false,
                },
              ],
        }));
        setNotice(
          "Demo lesson saved locally. Publish it to make it visible in Student Demo.",
        );
      },
      toggleLessonPublication: (id) => {
        update((current) => ({
          ...current,
          lessons: current.lessons.map((item) =>
            item.id === id ? { ...item, published: !item.published } : item,
          ),
        }));
        setNotice(
          "Demo lesson visibility updated. No real course content or notifications changed.",
        );
      },
      gradeSubmission: (id, score, feedback) => {
        const boundedScore = Math.max(0, Math.min(10, Math.round(score)));
        update((current) => ({
          ...current,
          submissions: current.submissions.map((item) =>
            item.id === id
              ? {
                  ...item,
                  status: "graded",
                  score: boundedScore,
                  feedback: feedback.trim(),
                }
              : item,
          ),
        }));
        setNotice(
          "Demo review completed. Guest Mode does not save grades, contact students, or send notifications.",
        );
      },
      sendDemoMessage: (text) => {
        const message = text.trim();
        if (!message) return;
        update((current) => ({
          ...current,
          messages: [
            ...current.messages,
            {
              id: `message-${Date.now()}`,
              author: "You (demo)",
              text: message,
              mine: true,
            },
            {
              id: `message-reply-${Date.now()}`,
              author: "Sample Study Partner",
              text: "Thanks — this local reply is part of the Guest Mode demonstration.",
              mine: false,
            },
          ],
        }));
        setNotice(
          "Demo message sent locally. Guest Mode does not contact real users.",
        );
      },
    }),
    [notice, role, state],
  );
  return <DemoContext.Provider value={value}>{children}</DemoContext.Provider>;
}

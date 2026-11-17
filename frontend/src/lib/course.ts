import { authRequest } from "./auth";

export type CourseStatus = "draft" | "published";
export type CourseQuestionLink = { question_id: number; position: number };
export type CourseLesson = {
  id: number;
  chapter_id: number;
  title: string;
  slug: string;
  content: string;
  position: number;
  status?: CourseStatus;
  questions: CourseQuestionLink[];
};
export type CourseChapter = {
  id: number;
  title: string;
  slug: string;
  position: number;
  status?: CourseStatus;
  lessons: CourseLesson[];
};
export type ChapterWrite = Pick<CourseChapter, "title" | "slug" | "position">;
export type LessonWrite = Pick<
  CourseLesson,
  "chapter_id" | "title" | "slug" | "content" | "position"
> & { questions: { question_id: number }[] };

export const courseApi = {
  publishedChapters: () => authRequest<CourseChapter[]>("/course/chapters"),
  publishedLesson: (lessonId: number) =>
    authRequest<CourseLesson>(`/course/lessons/${lessonId}`),
  managedChapters: () =>
    authRequest<CourseChapter[]>("/course/manage/chapters"),
  createChapter: (payload: ChapterWrite) =>
    authRequest<CourseChapter>("/course/chapters", "POST", payload),
  updateChapter: (id: number, payload: Partial<ChapterWrite>) =>
    authRequest<CourseChapter>(`/course/chapters/${id}`, "PATCH", payload),
  deleteChapter: (id: number) =>
    authRequest<void>(`/course/chapters/${id}`, "DELETE"),
  publishChapter: (id: number, publish: boolean) =>
    authRequest<CourseChapter>(
      `/course/chapters/${id}/${publish ? "publish" : "unpublish"}`,
      "POST",
    ),
  reorderChapters: (ids: number[]) =>
    authRequest<void>("/course/chapters/reorder", "PUT", { ids }),
  createLesson: (payload: LessonWrite) =>
    authRequest<CourseLesson>("/course/lessons", "POST", payload),
  updateLesson: (id: number, payload: Partial<LessonWrite>) =>
    authRequest<CourseLesson>(`/course/lessons/${id}`, "PATCH", payload),
  deleteLesson: (id: number) =>
    authRequest<void>(`/course/lessons/${id}`, "DELETE"),
  publishLesson: (id: number, publish: boolean) =>
    authRequest<CourseLesson>(
      `/course/lessons/${id}/${publish ? "publish" : "unpublish"}`,
      "POST",
    ),
  reorderLessons: (chapterId: number, ids: number[]) =>
    authRequest<void>(`/course/chapters/${chapterId}/lessons/reorder`, "PUT", {
      ids,
    }),
};

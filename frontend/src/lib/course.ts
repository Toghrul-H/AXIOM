import { apiFetch, authRequest, AuthRequestError } from "./auth";

export type CourseStatus = "draft" | "published";
export type CourseQuestionLink = { question_id: number; position: number };
export type CourseMaterial = {
  id: number;
  chapter_id: number | null;
  lesson_id: number | null;
  title: string;
  description: string | null;
  filename: string | null;
  media_type: string | null;
  size_bytes: number | null;
  sha256: string | null;
  storage_ready: boolean;
  status: CourseStatus;
  position: number;
  created_by_id: number;
  created_at: string;
  updated_at: string;
};
export type CourseMaterialPublic = Pick<
  CourseMaterial,
  | "id"
  | "title"
  | "description"
  | "filename"
  | "media_type"
  | "size_bytes"
  | "position"
> & { filename: string; media_type: string; size_bytes: number };
export type CourseLesson = {
  id: number;
  chapter_id: number;
  title: string;
  slug: string;
  content: string;
  position: number;
  status?: CourseStatus;
  questions: CourseQuestionLink[];
  materials: CourseMaterialPublic[];
};
export type CourseChapter = {
  id: number;
  title: string;
  slug: string;
  position: number;
  status?: CourseStatus;
  lessons: CourseLesson[];
  materials: CourseMaterialPublic[];
};
export type ChapterWrite = Pick<CourseChapter, "title" | "slug" | "position">;
export type LessonWrite = Pick<
  CourseLesson,
  "chapter_id" | "title" | "slug" | "content" | "position"
> & { questions: { question_id: number }[] };
export type MaterialWrite = {
  title: string;
  description?: string | null;
  chapter_id?: number;
  lesson_id?: number;
  position: number;
};

function errorFrom(response: Response) {
  return response
    .json()
    .catch(() => null)
    .then((data) => {
      throw new AuthRequestError(
        response.status,
        typeof data?.detail === "string"
          ? data.detail
          : "Course material request failed.",
      );
    });
}

export async function materialFile(id: number, action: "download" | "preview") {
  const response = await apiFetch(`/course/materials/${id}/${action}`);
  if (!response.ok) return errorFrom(response);
  const disposition = response.headers.get("content-disposition") ?? "";
  const filename =
    /filename="([^"]+)"/i.exec(disposition)?.[1] ?? "course-material";
  return {
    blob: await response.blob(),
    filename,
    mediaType:
      response.headers.get("content-type") ?? "application/octet-stream",
  };
}

export const courseApi = {
  publishedChapters: () => authRequest<CourseChapter[]>("/course/chapters"),
  publishedLesson: (lessonId: number) =>
    authRequest<CourseLesson>(`/course/lessons/${lessonId}`),
  managedChapters: () =>
    authRequest<CourseChapter[]>("/course/manage/chapters"),
  managedMaterials: () =>
    authRequest<CourseMaterial[]>("/course/manage/materials"),
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
  createMaterial: (payload: MaterialWrite) =>
    authRequest<CourseMaterial>("/course/materials", "POST", payload),
  updateMaterial: (
    id: number,
    payload: Partial<Pick<MaterialWrite, "title" | "description" | "position">>,
  ) => authRequest<CourseMaterial>(`/course/materials/${id}`, "PATCH", payload),
  deleteMaterial: (id: number) =>
    authRequest<void>(`/course/materials/${id}`, "DELETE"),
  publishMaterial: (id: number, publish: boolean) =>
    authRequest<CourseMaterial>(
      `/course/materials/${id}/${publish ? "publish" : "unpublish"}`,
      "POST",
    ),
  reorderMaterials: (
    parent: { chapterId?: number; lessonId?: number },
    ids: number[],
  ) => {
    const path = parent.chapterId
      ? `/course/chapters/${parent.chapterId}/materials/reorder`
      : `/course/lessons/${parent.lessonId}/materials/reorder`;
    return authRequest<void>(path, "PUT", { ids });
  },
  uploadMaterial: async (id: number, file: File) => {
    const response = await apiFetch(`/course/materials/${id}/file`, {
      method: "PUT",
      headers: {
        "Content-Type": file.type || "application/octet-stream",
        "X-Material-Filename": file.name,
      },
      body: file,
    });
    if (!response.ok) return errorFrom(response);
    return response.json() as Promise<CourseMaterial>;
  },
};

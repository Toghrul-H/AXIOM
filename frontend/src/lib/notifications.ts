import { authRequest } from "./auth";

export type NotificationValue = string | number | boolean | null;

export type AppNotification = {
  id: number;
  kind: string;
  payload: Record<string, NotificationValue>;
  link: string;
  created_at: string;
  read_at: string | null;
};

export type NotificationPage = {
  items: AppNotification[];
  next_cursor: string | null;
};

export type LegacyRecruitmentNotification = {
  id: number;
  title: string;
  body: string;
  link: string;
  created_at: string;
};

export const notificationApi = {
  list: (cursor?: string, signal?: AbortSignal) =>
    authRequest<NotificationPage>(
      `/notifications${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`,
      "GET",
      undefined,
      { signal },
    ),
  unreadCount: (signal?: AbortSignal) =>
    authRequest<{ count: number }>(
      "/notifications/unread-count",
      "GET",
      undefined,
      { signal },
    ),
  markRead: (notificationId: number) =>
    authRequest<AppNotification>(
      `/notifications/${notificationId}/read`,
      "POST",
    ),
  markAllRead: () => authRequest<void>("/notifications/read-all", "POST"),
  legacyRecruitment: (signal?: AbortSignal) =>
    authRequest<LegacyRecruitmentNotification[]>(
      "/recruitment/notifications/recruitment",
      "GET",
      undefined,
      { signal },
    ),
};

export function isSafeNotificationLink(link: string): boolean {
  return (
    link.startsWith("/") &&
    !link.startsWith("//") &&
    !link.includes("\\") &&
    !/[\u0000-\u001f]/.test(link)
  );
}

const copy: Record<string, { title: string; body: string }> = {
  STUDY_PARTNER_REQUEST_RECEIVED: {
    title: "New study partner request",
    body: "You have a new Study Partner request to review.",
  },
  STUDY_PARTNER_REQUEST_ACCEPTED: {
    title: "Study partner request accepted",
    body: "Your Study Partner request was accepted.",
  },
  STUDY_PARTNER_REQUEST_DECLINED: {
    title: "Study partner request declined",
    body: "Your Study Partner request was declined.",
  },
  STUDY_PARTNER_REQUEST_CANCELLED: {
    title: "Study partner request cancelled",
    body: "A Study Partner request was cancelled.",
  },
  STUDY_PARTNER_CHAT_MESSAGE: {
    title: "New Study Partner message",
    body: "You have a new message from a Study Partner.",
  },
  RECRUITMENT_VACANCY_OPEN: {
    title: "New demonstrator opportunity",
    body: "A new demonstrator vacancy is available.",
  },
  RECRUITMENT_APPLICATION_UNDER_REVIEW: {
    title: "Demonstrator application under review",
    body: "Your demonstrator application is now under review.",
  },
  RECRUITMENT_APPLICATION_ACCEPTED: {
    title: "Demonstrator application accepted",
    body: "Your demonstrator application has been accepted.",
  },
  RECRUITMENT_APPLICATION_REJECTED: {
    title: "Demonstrator application update",
    body: "Your demonstrator application was not selected.",
  },
  QUIZ_AVAILABLE: {
    title: "Quiz available",
    body: "A new quiz is ready for you.",
  },
  COURSE_CHAPTER_PUBLISHED: {
    title: "New course chapter",
    body: "A new course chapter has been published.",
  },
  COURSE_LESSON_PUBLISHED: {
    title: "New course lesson",
    body: "A new course lesson has been published.",
  },
  MANUAL_GRADING_COMPLETED: {
    title: "Manual grading completed",
    body: "Your graded submission is now available.",
  },
};

export function notificationCopy(notification: AppNotification) {
  const fallback = copy[notification.kind] ?? {
    title: "AXIOM notification",
    body: "There is an update for you in AXIOM.",
  };
  return {
    title:
      typeof notification.payload.title === "string"
        ? notification.payload.title
        : fallback.title,
    body:
      typeof notification.payload.body === "string"
        ? notification.payload.body
        : fallback.body,
  };
}

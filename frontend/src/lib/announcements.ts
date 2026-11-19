import { authRequest } from "./auth";

export type Announcement = {
  id: number;
  title: string;
  body: string;
  category: "IMPORTANT" | "GENERAL";
  link: string | null;
  pinned: boolean;
  published_at: string | null;
  created_at: string;
  updated_at: string;
  read_at: string | null;
  status?: "draft" | "published";
};
export type AnnouncementWrite = Pick<
  Announcement,
  "title" | "body" | "category" | "link" | "pinned"
>;

export const announcementsApi = {
  list: () => authRequest<Announcement[]>("/student/announcements"),
  markRead: (id: number) =>
    authRequest<Announcement>(`/student/announcements/${id}/read`, "POST"),
  managed: () => authRequest<Announcement[]>("/announcements"),
  create: (value: AnnouncementWrite) =>
    authRequest<Announcement>("/announcements", "POST", value),
  update: (id: number, value: AnnouncementWrite) =>
    authRequest<Announcement>(`/announcements/${id}`, "PUT", value),
  publish: (id: number) =>
    authRequest<Announcement>(`/announcements/${id}/publish`, "POST"),
  unpublish: (id: number) =>
    authRequest<Announcement>(`/announcements/${id}/unpublish`, "POST"),
  remove: (id: number) => authRequest<void>(`/announcements/${id}`, "DELETE"),
};

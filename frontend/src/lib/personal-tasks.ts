import { apiFetch } from "./auth";

export type PersonalTask = {
  id: number;
  title: string;
  due_date: string | null;
  completed: boolean;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type PersonalTaskWrite = Pick<
  PersonalTask,
  "title" | "due_date" | "completed"
>;

async function request<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await apiFetch(path, {
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(
      typeof data?.detail === "string"
        ? data.detail
        : "Tasks could not be updated. Please retry.",
    );
  }
  return response.status === 204
    ? (undefined as T)
    : ((await response.json()) as T);
}

export const personalTasksApi = {
  list: () => request<PersonalTask[]>("/student/tasks"),
  create: (task: PersonalTaskWrite) =>
    request<PersonalTask>("/student/tasks", "POST", task),
  update: (id: number, task: PersonalTaskWrite) =>
    request<PersonalTask>(`/student/tasks/${id}`, "PUT", task),
  remove: (id: number) => request<void>(`/student/tasks/${id}`, "DELETE"),
};

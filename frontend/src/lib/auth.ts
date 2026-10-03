export type Role = "STUDENT" | "DEMONSTRATOR" | "LECTURER" | "ADMIN";
export type User = {
  id: number;
  email: string;
  role: Role;
  is_active: boolean;
  created_at: string;
};
export type AuthState = { user: User; csrf_token: string };
let csrfToken: string | null = null;
export const homeFor = (user: User) =>
  user.role === "STUDENT" ? "/student" : "/teacher";
export function setAuth(state: AuthState | null) {
  csrfToken = state?.csrf_token ?? null;
}

export async function apiFetch(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  const method = init.method ?? "GET";
  if (!["GET", "HEAD", "OPTIONS"].includes(method) && csrfToken)
    headers.set("X-CSRF-Token", csrfToken);
  if (init.body) headers.set("Content-Type", "application/json");
  const response = await fetch(`/api${path}`, {
    ...init,
    headers,
    credentials: "same-origin",
    cache: "no-store",
  });
  if (
    response.status === 401 &&
    !["/auth/login", "/auth/register"].includes(path)
  ) {
    setAuth(null);
    window.dispatchEvent(new Event("dmi-auth-expired"));
  }
  return response;
}

export async function authRequest<T>(
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
    throw new AuthRequestError(
      response.status,
      typeof data?.detail === "string"
        ? data.detail
        : Array.isArray(data?.detail)
          ? data.detail
              .map((item: { msg?: string }) => item.msg ?? "Invalid input")
              .join(" ")
          : "Check your email and password (12–128 characters), then try again.",
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export class AuthRequestError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

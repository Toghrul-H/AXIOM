"use client";
import { createContext, useContext, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  apiFetch,
  authRequest,
  homeFor,
  setAuth,
  type AuthState,
  type User,
} from "@/lib/auth";
import { AppShell } from "./app-shell";

const Context = createContext<{
  user: User | null;
  studentView: boolean;
  enterStudentView: () => void;
  exitStudentView: () => void;
  signIn: (state: AuthState) => void;
  signOut: () => Promise<void>;
} | null>(null);
const STUDENT_VIEW_KEY = "axiom-student-view";
const canPreviewStudentView = (user: User | null) =>
  user !== null && ["LECTURER", "ADMIN"].includes(user.role);
export function useAuth() {
  const value = useContext(Context);
  if (!value) throw new Error("Missing authentication provider");
  return value;
}

export function authRouteAccess(path: string) {
  const verificationPage = path === "/verify-email" || path === "/check-email";
  const recoveryPage =
    path === "/forgot-password" || path === "/reset-password";
  const privacyPage = path === "/privacy";
  const demoPage = path === "/demo";
  return {
    verificationPage,
    privacyPage,
    demoPage,
    publicPage:
      path === "/login" ||
      path === "/register" ||
      demoPage ||
      privacyPage ||
      verificationPage ||
      recoveryPage,
    redirectAuthenticated: path === "/login" || path === "/register",
  };
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const {
    verificationPage,
    privacyPage,
    demoPage,
    publicPage,
    redirectAuthenticated,
  } = authRouteAccess(path);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(() => !demoPage);
  const [error, setError] = useState("");
  const [studentViewRequested, setStudentViewRequested] = useState(
    () =>
      typeof window !== "undefined" &&
      window.localStorage.getItem(STUDENT_VIEW_KEY) === "true",
  );
  useEffect(() => {
    if (demoPage) return;
    let alive = true;
    const expire = () => {
      if (alive) {
        setUser(null);
        setAuth(null);
      }
    };
    const restore = async () => {
      try {
        const response = await apiFetch("/auth/me");
        if (!alive) return;
        if (response.status === 401) {
          expire();
          setError("");
        } else if (!response.ok)
          throw new Error(
            "Authentication is unavailable. Check the backend and retry.",
          );
        else {
          const state: AuthState = await response.json();
          if (alive) {
            setAuth(state);
            setUser(state.user);
            setError("");
          }
        }
      } catch {
        if (alive) setError("Authentication is unavailable. Reload to retry.");
      } finally {
        if (alive) setLoading(false);
      }
    };
    void restore();
    window.addEventListener("dmi-auth-expired", expire);
    window.addEventListener("focus", restore);
    const timer = window.setInterval(restore, 60000);
    return () => {
      alive = false;
      clearInterval(timer);
      window.removeEventListener("focus", restore);
      window.removeEventListener("dmi-auth-expired", expire);
    };
  }, [demoPage]);
  useEffect(() => {
    if (loading || error) return;
    if (!user && !publicPage) router.replace("/login");
    if (user && (redirectAuthenticated || path === "/"))
      router.replace(homeFor(user));
  }, [loading, error, user, publicPage, redirectAuthenticated, path, router]);
  const signIn = (state: AuthState) => {
    setAuth(state);
    setUser(state.user);
    setStudentViewRequested(false);
    window.localStorage.removeItem(STUDENT_VIEW_KEY);
    setError("");
    router.replace(homeFor(state.user));
  };
  const enterStudentView = () => {
    if (!canPreviewStudentView(user)) return;
    window.localStorage.setItem(STUDENT_VIEW_KEY, "true");
    setStudentViewRequested(true);
    router.push("/student");
  };
  const exitStudentView = () => {
    window.localStorage.removeItem(STUDENT_VIEW_KEY);
    setStudentViewRequested(false);
    if (user) router.push(homeFor(user));
  };
  const signOut = async () => {
    await authRequest<void>("/auth/logout", "POST");
    setAuth(null);
    setUser(null);
    setStudentViewRequested(false);
    window.localStorage.removeItem(STUDENT_VIEW_KEY);
    router.replace("/login");
  };
  const studentView = studentViewRequested && canPreviewStudentView(user);
  let content: React.ReactNode;
  if (verificationPage || privacyPage || demoPage) content = children;
  else if (loading)
    content = (
      <main className="auth-page" role="status">
        Restoring your session…
      </main>
    );
  else if (publicPage && !user) content = children;
  else if (error)
    content = (
      <main className="auth-page" role="alert">
        {error}
      </main>
    );
  else if (!user)
    content = <main className="auth-page">Redirecting to sign in…</main>;
  else {
    const staffPath =
      path.startsWith("/teacher") || path.startsWith("/demonstrator");
    const previewingAsStudent =
      studentView &&
      (path === "/student" ||
        path.startsWith("/student/course") ||
        path.startsWith("/student/quizzes"));
    const forbidden =
      (staffPath && user.role === "STUDENT") ||
      (path.startsWith("/student") &&
        user.role !== "STUDENT" &&
        !previewingAsStudent) ||
      ((path.startsWith("/teacher/users") ||
        path.startsWith("/teacher/assessments") ||
        path.startsWith("/teacher/exams") ||
        path.startsWith("/teacher/course") ||
        path.startsWith("/teacher/practice-sheets") ||
        path.startsWith("/teacher/recruitment")) &&
        !["LECTURER", "ADMIN"].includes(user.role));
    content = (
      <AppShell>
        {forbidden ? (
          <section>
            <h1>Access denied</h1>
            <p>Your account does not have permission to open this page.</p>
            <Link href={homeFor(user)}>Return to your dashboard</Link>
          </section>
        ) : (
          children
        )}
      </AppShell>
    );
  }
  return (
    <Context.Provider
      value={{
        user,
        studentView,
        enterStudentView,
        exitStudentView,
        signIn,
        signOut,
      }}
    >
      {content}
    </Context.Provider>
  );
}

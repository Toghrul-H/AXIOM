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
  signIn: (state: AuthState) => void;
  signOut: () => Promise<void>;
} | null>(null);
export function useAuth() {
  const value = useContext(Context);
  if (!value) throw new Error("Missing authentication provider");
  return value;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const path = usePathname();
  const router = useRouter();
  const verificationPage = path === "/verify-email" || path === "/check-email";
  const publicPage =
    path === "/login" || path === "/register" || verificationPage;
  useEffect(() => {
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
  }, []);
  useEffect(() => {
    if (loading || error) return;
    if (!user && !publicPage) router.replace("/login");
    if (user && ((publicPage && !verificationPage) || path === "/"))
      router.replace(homeFor(user));
  }, [loading, error, user, publicPage, verificationPage, path, router]);
  const signIn = (state: AuthState) => {
    setAuth(state);
    setUser(state.user);
    setError("");
    router.replace(homeFor(state.user));
  };
  const signOut = async () => {
    await authRequest<void>("/auth/logout", "POST");
    setAuth(null);
    setUser(null);
    router.replace("/login");
  };
  let content: React.ReactNode;
  if (verificationPage) content = children;
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
    const forbidden =
      (staffPath && user.role === "STUDENT") ||
      (path.startsWith("/student") && user.role !== "STUDENT") ||
      (path.startsWith("/teacher/users") &&
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
    <Context.Provider value={{ user, signIn, signOut }}>
      {content}
    </Context.Provider>
  );
}

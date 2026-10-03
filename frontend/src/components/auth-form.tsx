"use client";
import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { authRequest, AuthRequestError, type AuthState } from "@/lib/auth";
import { useAuth } from "./auth-provider";
import { Wordmark } from "./wordmark";

export function AuthForm({ register = false }: { register?: boolean }) {
  const { signIn } = useAuth();
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [needsVerification, setNeedsVerification] = useState(false);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNeedsVerification(false);
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email")).trim();
    const password = String(form.get("password"));
    if (register && password !== form.get("confirm")) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      if (register) {
        await authRequest("/auth/register", "POST", { email, password });
        router.replace("/check-email?registered=1");
      } else
        signIn(
          await authRequest<AuthState>("/auth/login", "POST", {
            email,
            password,
          }),
        );
    } catch (e) {
      setNeedsVerification(
        e instanceof AuthRequestError &&
          e.status === 403 &&
          e.message === "Verify your email before signing in",
      );
      setError(e instanceof Error ? e.message : "Unable to sign in.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="auth-page auth-layout">
      <aside className="auth-identity" aria-label="AXIOM Discrete Mathematics">
        <Wordmark />
        <div className="auth-identity-copy">
          <p className="eyebrow">ELTE · FACULTY OF INFORMATICS</p>
          <h2>
            Build the logic.
            <br />
            See the structure.
            <br />
            Master the ideas.
          </h2>
          <p>A focused learning workspace for Discrete Mathematics I.</p>
        </div>
        <div className="auth-math" aria-hidden="true">
          <span>∀</span>
          <span className="auth-math-line" />
          <span>ideas → understanding</span>
        </div>
        <p className="auth-identity-footer">Logic. Structure. Possibility.</p>
      </aside>
      <div className="auth-form-area">
        <section className="panel auth-card">
          <p className="eyebrow">
            {register ? "JOIN YOUR COURSE" : "WELCOME BACK"}
          </p>
          <h1>{register ? "Create your account" : "Sign in"}</h1>
          {
            <>
              <p>
                {register
                  ? "Please register using your ELTE Faculty of Informatics email address (@inf.elte.hu)."
                  : "Continue to your course workspace."}
              </p>
              <form onSubmit={submit} className="auth-form">
                <label>
                  Email
                  <input
                    name="email"
                    type="email"
                    autoComplete="email"
                    required
                    maxLength={254}
                  />
                </label>
                <label>
                  Password
                  <input
                    name="password"
                    type="password"
                    autoComplete={
                      register ? "new-password" : "current-password"
                    }
                    required
                    minLength={12}
                    maxLength={128}
                  />
                </label>
                {register && (
                  <>
                    <p className="field-hint">
                      Use a unique password of 12–128 characters.
                    </p>
                    <label>
                      Confirm password
                      <input
                        name="confirm"
                        type="password"
                        autoComplete="new-password"
                        required
                        minLength={12}
                        maxLength={128}
                      />
                    </label>
                  </>
                )}
                {error && (
                  <p role="alert" className="error-message">
                    {error}
                  </p>
                )}
                {needsVerification && (
                  <Link href="/check-email">Resend verification email</Link>
                )}
                <button className="button button-primary" disabled={busy}>
                  {busy
                    ? "Please wait…"
                    : register
                      ? "Create account"
                      : "Sign in"}
                </button>
              </form>
              <p>
                {register ? "Already registered? " : "New here? "}
                <Link href={register ? "/login" : "/register"}>
                  {register ? "Sign in" : "Create an account"}
                </Link>
              </p>
            </>
          }
        </section>
        <p className="auth-form-footer">AXIOM · Discrete Mathematics I</p>
      </div>
    </main>
  );
}

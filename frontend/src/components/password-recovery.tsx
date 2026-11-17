"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Wordmark } from "./wordmark";
import {
  requestPasswordReset,
  resetPassword,
  type PasswordResetResult,
} from "@/lib/password-recovery";

function Frame({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <main className="auth-page">
      <section className="panel auth-card">
        <Wordmark />
        <h1>{title}</h1>
        {children}
        <p>
          <Link href="/login">Back to sign in</Link>
        </p>
      </section>
    </main>
  );
}

export function ForgotPassword() {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const email = String(new FormData(event.currentTarget).get("email")).trim();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      setMessage(await requestPasswordReset(email));
    } catch {
      setError("Password reset is unavailable. Please try again shortly.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Frame title="Reset your password">
      <p>
        Enter your email address. If an eligible account exists, we will send
        password reset instructions.
      </p>
      <form className="auth-form" onSubmit={submit}>
        <label>
          Email
          <input
            name="email"
            type="email"
            autoComplete="email"
            required
            maxLength={254}
            disabled={busy || Boolean(message)}
          />
        </label>
        <button
          className="button button-primary"
          disabled={busy || Boolean(message)}
        >
          {busy ? "Requesting…" : "Send reset instructions"}
        </button>
      </form>
      {message && <p role="status">{message}</p>}
      {error && (
        <p role="alert" className="error-message">
          {error}
        </p>
      )}
    </Frame>
  );
}

type TokenState = "checking" | "ready" | "missing";

export function ResetPassword() {
  const token = useRef<string | null>(null);
  const initialized = useRef(false);
  const [tokenState, setTokenState] = useState<TokenState>("checking");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<PasswordResetResult | null>(null);
  const [validationError, setValidationError] = useState("");

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    let alive = true;
    void Promise.resolve().then(() => {
      token.current = new URL(window.location.href).searchParams.get("token");
      // Keep the secret in memory only and remove it from history immediately.
      window.history.replaceState(window.history.state, "", "/reset-password");
      if (alive)
        setTokenState(
          token.current && /^[A-Za-z0-9_-]{43}$/.test(token.current)
            ? "ready"
            : "missing",
        );
    });
    return () => {
      alive = false;
    };
  }, []);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || tokenState !== "ready") return;
    const form = new FormData(event.currentTarget);
    const password = String(form.get("password"));
    const confirmation = String(form.get("confirmation"));
    setValidationError("");
    setResult(null);
    if (password.length < 12 || password.length > 128) {
      setValidationError("Use a password of 12–128 characters.");
      return;
    }
    if (password !== confirmation) {
      setValidationError("Passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      setResult(await resetPassword(token.current, password));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Frame title="Choose a new password">
      {tokenState === "checking" && <p role="status">Checking your link…</p>}
      {tokenState === "missing" && (
        <p role="alert" className="error-message">
          This password reset link is invalid or has expired.
        </p>
      )}
      {tokenState === "ready" && result?.kind !== "success" && (
        <form className="auth-form" onSubmit={submit}>
          <label>
            New password
            <input
              name="password"
              type="password"
              autoComplete="new-password"
              required
              minLength={12}
              maxLength={128}
              disabled={busy}
            />
          </label>
          <p className="field-hint">
            Use a unique password of 12–128 characters.
          </p>
          <label>
            Confirm new password
            <input
              name="confirmation"
              type="password"
              autoComplete="new-password"
              required
              minLength={12}
              maxLength={128}
              disabled={busy}
            />
          </label>
          {validationError && (
            <p role="alert" className="error-message">
              {validationError}
            </p>
          )}
          {result && (
            <p
              role={result.kind === "error" ? "alert" : "status"}
              className={result.kind === "error" ? "error-message" : undefined}
            >
              {result.message}
            </p>
          )}
          <button className="button button-primary" disabled={busy}>
            {busy ? "Resetting…" : "Reset password"}
          </button>
        </form>
      )}
      {result?.kind === "success" && <p role="status">{result.message}</p>}
    </Frame>
  );
}

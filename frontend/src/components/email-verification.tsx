"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Wordmark } from "./wordmark";
import {
  resendVerification,
  verifyEmail,
  type VerificationResult,
} from "@/lib/email-verification";

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
          <Link href="/login">Sign in</Link>
        </p>
      </section>
    </main>
  );
}

export function VerifyEmail() {
  const [result, setResult] = useState<VerificationResult | null>(null);
  const token = useRef<string | null>(null);
  const pending = useRef<Promise<VerificationResult> | null>(null);
  useEffect(() => {
    let alive = true;
    if (!pending.current) {
      token.current = new URL(window.location.href).searchParams.get("token");
      // Remove the secret from browser history immediately; keep only in memory.
      window.history.replaceState(window.history.state, "", "/verify-email");
      pending.current = verifyEmail(token.current);
    }
    void pending.current.then((value) => {
      if (alive) setResult(value);
    });
    return () => {
      alive = false;
    };
  }, []);
  async function retry() {
    setResult(null);
    setResult(await verifyEmail(token.current));
  }
  return (
    <Frame title="Verify your email">
      <p role={result?.kind === "success" || !result ? "status" : "alert"}>
        {result?.message ?? "Verifying your email…"}
      </p>
      {result?.kind === "success" ? (
        <p>Your account is ready. Sign in to access your Student dashboard.</p>
      ) : (
        result && (
          <p>
            <Link href="/check-email">Request another verification email</Link>
          </p>
        )
      )}
      {result?.kind === "error" && (
        <button className="button button-primary" onClick={retry}>
          Retry verification
        </button>
      )}
    </Frame>
  );
}

export function CheckEmail({ registered }: { registered: boolean }) {
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
      setMessage(await resendVerification(email));
    } catch {
      setError(
        "Unable to request verification. Please wait a minute and try again.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <Frame title="Check your email">
      {registered && (
        <p role="status">
          Your Student account was created and a verification email was sent.
        </p>
      )}
      <p>
        Check your @inf.elte.hu inbox and spam folder. Verify your email before
        signing in.
      </p>
      <p>Need another email? Enter your ELTE Faculty of Informatics address.</p>
      <form className="auth-form" onSubmit={submit}>
        <label>
          Email
          <input
            name="email"
            type="email"
            autoComplete="email"
            required
            maxLength={254}
            pattern="[^@]+@[iI][nN][fF]\.[eE][lL][tT][eE]\.[hH][uU]"
            title="Use your @inf.elte.hu email address"
          />
        </label>
        <button className="button button-primary" disabled={busy}>
          {busy ? "Requesting…" : "Resend verification email"}
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

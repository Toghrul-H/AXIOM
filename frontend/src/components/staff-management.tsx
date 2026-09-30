"use client";
import { useEffect, useState } from "react";
import { authRequest, type User, type Role } from "@/lib/auth";
import { useAuth } from "./auth-provider";
import { PageHeading } from "./page-heading";

export function StaffManagement() {
  const { user } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [version, setVersion] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    let alive = true;
    authRequest<User[]>(
      `/users?q=${encodeURIComponent(search)}&offset=${offset}&limit=20`,
    )
      .then((data) => {
        if (alive) setUsers(data);
      })
      .catch((e) => {
        if (alive) setError(e.message);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [search, offset, version]);
  async function change(
    target: User,
    body: { role: Role } | { is_active: boolean },
  ) {
    const action =
      "role" in body
        ? `Change ${target.email} from ${target.role} to ${body.role}`
        : `${body.is_active ? "Reactivate" : "Deactivate"} account ${target.email}`;
    if (
      !window.confirm(
        `${action}? Existing sessions will be revoked. History is preserved.`,
      )
    )
      return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await authRequest(
        `/users/${target.id}/${"role" in body ? "role" : "status"}`,
        "POST",
        body,
      );
      setNotice(`${action}: done. The user must sign in again.`);
      setVersion((v) => v + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update account.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="ACCOUNTS"
        title="Staff Management"
        description="Ask a colleague to register, then find their account and assign an authorized role."
      />
      <p>
        Account changes preserve quiz history and require the affected user to
        sign in again.
      </p>
      <form
        className="staff-search"
        onSubmit={(e) => {
          e.preventDefault();
          setLoading(true);
          setError("");
          setOffset(0);
          setSearch(query);
          setVersion((v) => v + 1);
        }}
      >
        <label>
          Find by email
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            maxLength={254}
          />
        </label>
        <button className="button button-secondary">Search</button>
      </form>
      {error && (
        <p role="alert" className="error-message">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {loading ? (
        <p role="status">Loading accounts…</p>
      ) : (
        <div className="staff-list">
          {users.length === 0 && <p>No matching accounts.</p>}
          {users.map((target) => (
            <article className="panel staff-row" key={target.id}>
              <div>
                <h2>{target.email}</h2>
                <p>
                  {target.role} · {target.is_active ? "Active" : "Inactive"}
                </p>
              </div>
              <div className="staff-actions">
                {target.role === "STUDENT" && (
                  <button
                    className="button button-secondary"
                    disabled={busy}
                    onClick={() => change(target, { role: "DEMONSTRATOR" })}
                  >
                    Promote to Demonstrator
                  </button>
                )}
                {user?.role === "ADMIN" && target.role !== "LECTURER" && (
                  <button
                    className="button button-secondary"
                    disabled={busy}
                    onClick={() => change(target, { role: "LECTURER" })}
                  >
                    Promote to Lecturer
                  </button>
                )}
                {target.role === "LECTURER" && user?.role === "ADMIN" && (
                  <button
                    className="button button-secondary"
                    disabled={busy}
                    onClick={() => change(target, { role: "DEMONSTRATOR" })}
                  >
                    Change to Demonstrator
                  </button>
                )}
                {target.role !== "STUDENT" && (
                  <button
                    className="button button-secondary"
                    disabled={busy}
                    onClick={() => change(target, { role: "STUDENT" })}
                  >
                    Change to Student
                  </button>
                )}
                {(target.role === "DEMONSTRATOR" || user?.role === "ADMIN") && (
                  <button
                    className="button button-secondary"
                    disabled={busy}
                    onClick={() =>
                      change(target, { is_active: !target.is_active })
                    }
                  >
                    {target.is_active
                      ? "Deactivate Account"
                      : "Reactivate Account"}
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
      <div className="staff-actions">
        <button
          className="button button-secondary"
          disabled={loading || offset === 0}
          onClick={() => {
            setLoading(true);
            setOffset(Math.max(0, offset - 20));
          }}
        >
          Previous
        </button>
        <button
          className="button button-secondary"
          disabled={loading || users.length < 20}
          onClick={() => {
            setLoading(true);
            setOffset(offset + 20);
          }}
        >
          Next
        </button>
      </div>
    </>
  );
}

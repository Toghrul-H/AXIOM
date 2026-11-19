"use client";
import { FormEvent, useEffect, useState } from "react";
import {
  announcementsApi,
  type Announcement,
  type AnnouncementWrite,
} from "@/lib/announcements";
import { PageHeading } from "./page-heading";

const blank: AnnouncementWrite = {
  title: "",
  body: "",
  category: "GENERAL",
  link: null,
  pinned: false,
};
export function AnnouncementManager() {
  const [items, setItems] = useState<Announcement[] | null>(null);
  const [draft, setDraft] = useState<AnnouncementWrite>(blank);
  const [editing, setEditing] = useState<Announcement | null>(null);
  const [filter, setFilter] = useState<"all" | "draft" | "published">("all");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const load = async () => {
    try {
      setItems(await announcementsApi.managed());
      setError("");
    } catch {
      setError("Announcements could not be loaded.");
    }
  };
  useEffect(() => {
    const initial = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(initial);
  }, []);
  const reset = () => {
    setEditing(null);
    setDraft(blank);
  };
  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const value = editing
        ? await announcementsApi.update(editing.id, draft)
        : await announcementsApi.create(draft);
      setItems((current) =>
        editing
          ? (current ?? []).map((item) => (item.id === value.id ? value : item))
          : [value, ...(current ?? [])],
      );
      reset();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Announcement could not be saved.",
      );
    } finally {
      setBusy(false);
    }
  };
  const transition = async (
    item: Announcement,
    action: "publish" | "unpublish" | "remove",
  ) => {
    if (
      busy ||
      (action === "remove" && !window.confirm(`Delete “${item.title}”?`))
    )
      return;
    setBusy(true);
    setError("");
    try {
      if (action === "remove") {
        await announcementsApi.remove(item.id);
        setItems((current) =>
          (current ?? []).filter((entry) => entry.id !== item.id),
        );
      } else {
        const value = await announcementsApi[action](item.id);
        setItems((current) =>
          (current ?? []).map((entry) =>
            entry.id === item.id ? value : entry,
          ),
        );
      }
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Announcement could not be updated.",
      );
    } finally {
      setBusy(false);
    }
  };
  const visible = (items ?? []).filter(
    (item) => filter === "all" || item.status === filter,
  );
  return (
    <section className="announcement-manager">
      <PageHeading
        eyebrow="COURSE COMMUNICATION"
        title="Announcements"
        description="Prepare, publish, and manage student-facing course updates."
      />
      <form
        className="panel announcement-form"
        onSubmit={(event) => void save(event)}
      >
        <h2>{editing ? "Edit draft" : "New announcement"}</h2>
        <label>
          Title
          <input
            required
            maxLength={200}
            value={draft.title}
            onChange={(event) =>
              setDraft({ ...draft, title: event.target.value })
            }
          />
        </label>
        <label>
          Message
          <textarea
            required
            maxLength={20000}
            value={draft.body}
            onChange={(event) =>
              setDraft({ ...draft, body: event.target.value })
            }
          />
        </label>
        <div className="announcement-fields">
          <label>
            Category
            <select
              value={draft.category}
              onChange={(event) =>
                setDraft({
                  ...draft,
                  category: event.target.value as AnnouncementWrite["category"],
                })
              }
            >
              <option value="GENERAL">General</option>
              <option value="IMPORTANT">Important</option>
            </select>
          </label>
          <label>
            Internal link (optional)
            <input
              placeholder="/student/course"
              value={draft.link ?? ""}
              onChange={(event) =>
                setDraft({ ...draft, link: event.target.value || null })
              }
            />
          </label>
          <label className="option-row">
            <input
              type="checkbox"
              checked={draft.pinned}
              onChange={(event) =>
                setDraft({ ...draft, pinned: event.target.checked })
              }
            />{" "}
            Pin announcement
          </label>
        </div>
        <div className="quiz-actions">
          <button className="button button-primary" disabled={busy}>
            {busy ? "Saving…" : editing ? "Save draft" : "Save draft"}
          </button>
          {editing && (
            <button
              className="button button-secondary"
              type="button"
              onClick={reset}
            >
              Cancel
            </button>
          )}
        </div>
      </form>
      <div className="section-heading">
        <h2>All announcements</h2>
        <select
          aria-label="Filter announcements"
          value={filter}
          onChange={(event) => setFilter(event.target.value as typeof filter)}
        >
          <option value="all">All</option>
          <option value="draft">Drafts</option>
          <option value="published">Published</option>
        </select>
      </div>
      {error && <p role="alert">{error}</p>}
      {items === null ? (
        <p role="status">Loading announcements…</p>
      ) : visible.length === 0 ? (
        <p className="empty-inline">No matching announcements.</p>
      ) : (
        <div className="announcement-list">
          {visible.map((item) => (
            <article className="panel announcement-row" key={item.id}>
              <div>
                <span
                  className={`announcement-category ${item.category.toLowerCase()}`}
                >
                  {item.category === "IMPORTANT" ? "Important" : "General"}
                </span>
                <h3>
                  {item.pinned ? "Pinned · " : ""}
                  {item.title}
                </h3>
                <p>{item.body}</p>
                <small>
                  {item.status} {item.link ? `· ${item.link}` : ""}
                </small>
              </div>
              <div className="announcement-actions">
                {item.status === "draft" && (
                  <>
                    <button
                      className="button button-secondary"
                      disabled={busy}
                      onClick={() => {
                        setEditing(item);
                        setDraft({
                          title: item.title,
                          body: item.body,
                          category: item.category,
                          link: item.link,
                          pinned: item.pinned,
                        });
                      }}
                    >
                      Edit
                    </button>
                    <button
                      className="button button-primary"
                      disabled={busy}
                      onClick={() => void transition(item, "publish")}
                    >
                      Publish
                    </button>
                  </>
                )}
                {item.status === "published" && (
                  <button
                    className="button button-secondary"
                    disabled={busy}
                    onClick={() => void transition(item, "unpublish")}
                  >
                    Unpublish
                  </button>
                )}
                <button
                  className="button button-danger"
                  disabled={busy}
                  onClick={() => void transition(item, "remove")}
                >
                  Delete
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

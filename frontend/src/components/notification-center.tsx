"use client";

import { Bell, Check, LoaderCircle } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  type AppNotification,
  type LegacyRecruitmentNotification,
  isSafeNotificationLink,
  notificationApi,
  notificationCopy,
} from "@/lib/notifications";

type DisplayNotification =
  | { source: "unified"; value: AppNotification }
  | { source: "legacy"; value: LegacyRecruitmentNotification };

function formattedTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Recently"
    : new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(date);
}

function isDuplicatedLegacy(
  legacy: LegacyRecruitmentNotification,
  notifications: AppNotification[],
) {
  const legacyTime = new Date(legacy.created_at).getTime();
  return notifications.some((notification) => {
    if (
      !notification.kind.startsWith("RECRUITMENT_") ||
      notification.link !== legacy.link
    )
      return false;
    return (
      Math.abs(new Date(notification.created_at).getTime() - legacyTime) < 5_000
    );
  });
}

export function NotificationCenter({ userId }: { userId: number }) {
  const router = useRouter();
  const [items, setItems] = useState<AppNotification[]>([]);
  const [legacy, setLegacy] = useState<LegacyRecruitmentNotification[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const [markingAll, setMarkingAll] = useState(false);
  const pending = useRef(false);
  const controller = useRef<AbortController | null>(null);
  const cursorRef = useRef<string | null>(null);

  const load = useCallback(async (mode: "replace" | "append" = "replace") => {
    if (pending.current) return;
    pending.current = true;
    const aborter = new AbortController();
    controller.current?.abort();
    controller.current = aborter;
    if (mode === "replace") setLoading(true);
    else setLoadingMore(true);
    try {
      const page = await notificationApi.list(
        mode === "append" ? (cursorRef.current ?? undefined) : undefined,
        aborter.signal,
      );
      if (aborter.signal.aborted) return;
      const count = await notificationApi.unreadCount(aborter.signal);
      if (aborter.signal.aborted) return;
      setItems((current) =>
        mode === "append"
          ? [
              ...current,
              ...page.items.filter(
                (item) => !current.some((known) => known.id === item.id),
              ),
            ]
          : page.items,
      );
      setCursor(page.next_cursor);
      cursorRef.current = page.next_cursor;
      setUnread(count.count);
      setError("");
      if (mode === "replace") {
        try {
          const historic = await notificationApi.legacyRecruitment(
            aborter.signal,
          );
          if (!aborter.signal.aborted) setLegacy(historic);
        } catch {
          if (!aborter.signal.aborted) setLegacy([]);
        }
      }
    } catch {
      if (!aborter.signal.aborted) {
        setError("Notifications could not be loaded. Please retry.");
        if (mode === "replace") {
          try {
            const historic = await notificationApi.legacyRecruitment(
              aborter.signal,
            );
            if (!aborter.signal.aborted) setLegacy(historic);
          } catch {
            // A signed-in user can retry without exposing transport details.
          }
        }
      }
    } finally {
      if (!aborter.signal.aborted) {
        pending.current = false;
        setLoading(false);
        setLoadingMore(false);
      }
    }
  }, []);

  useEffect(() => {
    const initial = window.setTimeout(() => void load(), 0);
    const refresh = () => {
      if (!document.hidden) void load();
    };
    const timer = window.setInterval(refresh, 30_000);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      controller.current?.abort();
      clearTimeout(initial);
      clearInterval(timer);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [userId, load]);

  const display = [
    ...items.map((value): DisplayNotification => ({
      source: "unified",
      value,
    })),
    ...legacy
      .filter((item) => !isDuplicatedLegacy(item, items))
      .map((value): DisplayNotification => ({ source: "legacy", value })),
  ].sort(
    (left, right) =>
      new Date(right.value.created_at).getTime() -
      new Date(left.value.created_at).getTime(),
  );

  const open = async (item: DisplayNotification) => {
    const link = item.value.link;
    if (!isSafeNotificationLink(link)) return;
    if (item.source === "unified" && item.value.read_at === null) {
      try {
        await notificationApi.markRead(item.value.id);
        setItems((current) =>
          current.map((notification) =>
            notification.id === item.value.id
              ? { ...notification, read_at: new Date().toISOString() }
              : notification,
          ),
        );
        setUnread((count) => Math.max(0, count - 1));
      } catch {
        // Navigation remains available even if the read receipt is delayed.
      }
    }
    router.push(link);
  };

  const markAll = async () => {
    if (markingAll || unread === 0) return;
    setMarkingAll(true);
    try {
      await notificationApi.markAllRead();
      const readAt = new Date().toISOString();
      setItems((current) =>
        current.map((item) => ({ ...item, read_at: readAt })),
      );
      setUnread(0);
    } catch {
      setError("Notifications could not be marked as read. Please retry.");
    } finally {
      setMarkingAll(false);
    }
  };

  const badge = unread > 99 ? "99+" : String(unread);
  return (
    <details className="account-control notification-control">
      <summary
        aria-label={unread ? `${unread} unread notifications` : "Notifications"}
      >
        <Bell size={20} />
        {unread > 0 && (
          <span className="notification-badge" aria-hidden="true">
            {badge}
          </span>
        )}
      </summary>
      <section
        className="account-menu notification-menu"
        aria-label="Notifications"
      >
        <header>
          <strong>Notifications</strong>
          <button
            className="notification-read-all"
            onClick={() => void markAll()}
            disabled={markingAll || unread === 0}
          >
            {markingAll ? (
              <LoaderCircle size={14} className="spin" />
            ) : (
              <Check size={14} />
            )}
            Mark all read
          </button>
        </header>
        {loading ? (
          <p role="status">Loading notifications…</p>
        ) : error && display.length === 0 ? (
          <div role="alert">
            <p>{error}</p>
            <button
              className="button button-secondary"
              onClick={() => void load()}
            >
              Retry
            </button>
          </div>
        ) : display.length ? (
          <div className="notification-list">
            {display.map((item) => {
              const isUnified = item.source === "unified";
              const copy = isUnified
                ? notificationCopy(item.value)
                : item.value;
              const unreadItem = isUnified && item.value.read_at === null;
              return (
                <button
                  key={`${item.source}-${item.value.id}`}
                  className={`notification-item ${unreadItem ? "is-unread" : ""}`}
                  onClick={() => void open(item)}
                  disabled={!isSafeNotificationLink(item.value.link)}
                >
                  <span>
                    <strong>{copy.title}</strong>
                    <small>{copy.body}</small>
                  </span>
                  <time dateTime={item.value.created_at}>
                    {formattedTime(item.value.created_at)}
                  </time>
                </button>
              );
            })}
          </div>
        ) : (
          <p>No notifications yet.</p>
        )}
        {error && display.length > 0 && <p role="alert">{error}</p>}
        {cursor && (
          <button
            className="button button-secondary"
            disabled={loadingMore}
            onClick={() => void load("append")}
          >
            {loadingMore ? "Loading…" : "Load more"}
          </button>
        )}
      </section>
    </details>
  );
}

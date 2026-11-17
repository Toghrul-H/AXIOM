"use client";

import { useCallback, useEffect, useState } from "react";

import type { Topic } from "@/lib/questions";
import {
  type StudyFormat,
  type StudyPartnerPublicProfile,
  type StudyPartnerRequest,
  type StudyPartnerRequestStatus,
  studyPartnerApi,
} from "@/lib/study-partner";

const statusLabel: Record<StudyPartnerRequestStatus, string> = {
  PENDING: "Pending",
  ACCEPTED: "Accepted",
  DECLINED: "Declined",
  CANCELLED: "Cancelled",
};

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

function TopicList({
  title,
  topics,
}: {
  title: string;
  topics: StudyPartnerPublicProfile["shared_study_topics"];
}) {
  if (!topics.length) return null;
  return (
    <p className="study-partner-topic-summary">
      <strong>{title}:</strong> {topics.map((topic) => topic.name).join(", ")}
    </p>
  );
}

export function StudyPartnerDiscovery({
  topics,
  enabled,
  refreshKey,
  onActivity,
}: {
  topics: Topic[];
  enabled: boolean;
  refreshKey: number;
  onActivity: () => void;
}) {
  const [items, setItems] = useState<StudyPartnerPublicProfile[]>([]);
  const [recentlyBlocked, setRecentlyBlocked] = useState<
    StudyPartnerPublicProfile[]
  >([]);
  const [topicId, setTopicId] = useState("");
  const [studyFormat, setStudyFormat] = useState<StudyFormat | "">("");
  const [loading, setLoading] = useState(false);
  const [sendingTo, setSendingTo] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError("");
    try {
      setItems(
        await studyPartnerApi.partners({
          topicIds: topicId ? [Number(topicId)] : [],
          studyFormat: studyFormat || undefined,
        }),
      );
    } catch (loadError) {
      setError(errorMessage(loadError, "Partners could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, [enabled, studyFormat, topicId]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load, refreshKey]);

  async function sendRequest(profileId: number) {
    if (sendingTo !== null) return;
    setSendingTo(profileId);
    setError("");
    setMessage("");
    try {
      await studyPartnerApi.sendRequest(profileId);
      setMessage("Study request sent.");
      onActivity();
    } catch (requestError) {
      setError(
        errorMessage(requestError, "The study request could not be sent."),
      );
    } finally {
      setSendingTo(null);
    }
  }

  async function block(profile: StudyPartnerPublicProfile) {
    if (
      !window.confirm(
        `Block ${profile.display_name}? They will no longer appear in discovery, and any pending request between you will be cancelled.`,
      )
    )
      return;
    setSendingTo(profile.profile_id);
    setError("");
    try {
      await studyPartnerApi.block(profile.profile_id);
      setMessage(`${profile.display_name} has been blocked.`);
      setItems((current) =>
        current.filter((item) => item.profile_id !== profile.profile_id),
      );
      setRecentlyBlocked((current) => [
        ...current.filter((item) => item.profile_id !== profile.profile_id),
        profile,
      ]);
      onActivity();
    } catch (blockError) {
      setError(errorMessage(blockError, "The student could not be blocked."));
    } finally {
      setSendingTo(null);
    }
  }

  async function unblock(profile: StudyPartnerPublicProfile) {
    setSendingTo(profile.profile_id);
    setError("");
    try {
      await studyPartnerApi.unblock(profile.profile_id);
      setRecentlyBlocked((current) =>
        current.filter((item) => item.profile_id !== profile.profile_id),
      );
      setMessage(`${profile.display_name} has been unblocked.`);
      await load();
    } catch (unblockError) {
      setError(
        errorMessage(unblockError, "The student could not be unblocked."),
      );
    } finally {
      setSendingTo(null);
    }
  }

  return (
    <section
      className="study-partner-section"
      aria-labelledby="partner-discovery"
    >
      <div className="panel-heading">
        <div>
          <p className="eyebrow">DISCOVER</p>
          <h2 id="partner-discovery">Find study partners</h2>
        </div>
      </div>
      {!enabled ? (
        <div className="panel empty-state">
          <h3>Activate Study Partner to browse profiles</h3>
          <p>Save an active profile above before discovering other students.</p>
        </div>
      ) : (
        <>
          <div className="study-partner-filters" aria-label="Partner filters">
            <label>
              Topic
              <select
                value={topicId}
                onChange={(event) => setTopicId(event.target.value)}
              >
                <option value="">All topics</option>
                {topics.map((topic) => (
                  <option key={topic.id} value={topic.id}>
                    {topic.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Study format
              <select
                value={studyFormat}
                onChange={(event) =>
                  setStudyFormat(event.target.value as StudyFormat | "")
                }
              >
                <option value="">All formats</option>
                <option value="ONLINE">Online</option>
                <option value="IN_PERSON">In person</option>
                <option value="EITHER">Either</option>
              </select>
            </label>
          </div>
          {error && (
            <p className="error-message" role="alert">
              {error}
            </p>
          )}
          {message && (
            <p className="success-message" role="status">
              {message}
            </p>
          )}
          {loading ? (
            <p className="panel loading-state" role="status">
              Loading partners…
            </p>
          ) : items.length ? (
            <div className="study-partner-card-list">
              {items.map((partner) => (
                <article
                  className="panel study-partner-card"
                  key={partner.profile_id}
                >
                  <div className="study-partner-card-heading">
                    <h3>{partner.display_name}</h3>
                    <span className="recruitment-status status-submitted">
                      {partner.study_format === "IN_PERSON"
                        ? "IN PERSON"
                        : partner.study_format}
                    </span>
                  </div>
                  {partner.introduction && <p>{partner.introduction}</p>}
                  <TopicList
                    title="Shared study topics"
                    topics={partner.shared_study_topics}
                  />
                  <TopicList
                    title="Complementary topics"
                    topics={partner.complementary_topics}
                  />
                  <p className="field-hint">
                    {partner.has_compatible_availability
                      ? "Your saved availability overlaps. Exact schedules stay private."
                      : "No availability overlap is currently recorded."}
                  </p>
                  <div className="quiz-actions">
                    <button
                      className="button button-primary"
                      disabled={sendingTo !== null}
                      onClick={() => void sendRequest(partner.profile_id)}
                    >
                      {sendingTo === partner.profile_id
                        ? "Working…"
                        : "Send request"}
                    </button>
                    <button
                      className="button button-secondary"
                      disabled={sendingTo !== null}
                      onClick={() => void block(partner)}
                    >
                      Block
                    </button>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="panel empty-state">
              <h3>No study partners match these filters.</h3>
              <p>Try another topic or study format later.</p>
            </div>
          )}
          {recentlyBlocked.length > 0 && (
            <section
              className="panel study-partner-recent-blocks"
              aria-label="Recently blocked students"
            >
              <h3>Recently blocked</h3>
              <p className="field-hint">
                Unblock a student if this was a mistake. Existing blocks cannot
                be listed after this page is refreshed.
              </p>
              {recentlyBlocked.map((profile) => (
                <div
                  className="study-partner-recent-block"
                  key={profile.profile_id}
                >
                  <span>{profile.display_name}</span>
                  <button
                    className="button button-secondary"
                    disabled={sendingTo !== null}
                    onClick={() => void unblock(profile)}
                  >
                    {sendingTo === profile.profile_id ? "Working…" : "Unblock"}
                  </button>
                </div>
              ))}
            </section>
          )}
          {error && (
            <button
              className="button button-secondary"
              onClick={() => void load()}
            >
              Retry
            </button>
          )}
        </>
      )}
    </section>
  );
}

export function StudyPartnerRequests({
  refreshKey,
  onActivity,
}: {
  refreshKey: number;
  onActivity: () => void;
}) {
  const [incoming, setIncoming] = useState<StudyPartnerRequest[]>([]);
  const [outgoing, setOutgoing] = useState<StudyPartnerRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [nextIncoming, nextOutgoing] = await Promise.all([
        studyPartnerApi.requests("incoming"),
        studyPartnerApi.requests("outgoing"),
      ]);
      setIncoming(nextIncoming);
      setOutgoing(nextOutgoing);
    } catch (loadError) {
      setError(errorMessage(loadError, "Study requests could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load, refreshKey]);

  async function act(
    request: StudyPartnerRequest,
    action: "accept" | "decline" | "cancel" | "block",
  ) {
    const prompt =
      action === "decline"
        ? `Decline the request from ${request.counterpart.display_name}?`
        : action === "cancel"
          ? `Cancel your request to ${request.counterpart.display_name}?`
          : action === "block"
            ? `Block ${request.counterpart.display_name}? Pending requests will be cancelled.`
            : "";
    if (prompt && !window.confirm(prompt)) return;
    setBusy(request.id);
    setError("");
    try {
      if (action === "accept") await studyPartnerApi.accept(request.id);
      if (action === "decline") await studyPartnerApi.decline(request.id);
      if (action === "cancel") await studyPartnerApi.cancel(request.id);
      if (action === "block")
        await studyPartnerApi.block(request.counterpart.profile_id);
      setMessage(
        action === "accept"
          ? "Study request accepted."
          : action === "decline"
            ? "Study request declined."
            : action === "cancel"
              ? "Study request cancelled."
              : `${request.counterpart.display_name} has been blocked.`,
      );
      await load();
      onActivity();
    } catch (actionError) {
      setError(
        errorMessage(actionError, "Study request could not be updated."),
      );
    } finally {
      setBusy(null);
    }
  }

  function requestRows({
    items,
    direction,
  }: {
    items: StudyPartnerRequest[];
    direction: "incoming" | "outgoing";
  }) {
    if (!items.length) {
      return <p className="empty-inline">No {direction} study requests.</p>;
    }

    return (
      <div className="recruitment-list">
        {items.map((request) => (
          <article className="recruitment-row" key={request.id}>
            <div>
              <strong>{request.counterpart.display_name}</strong>
              <p>
                {direction === "incoming"
                  ? "Sent you a Study Partner request."
                  : "You sent a Study Partner request."}
              </p>
              <small>
                Updated {new Date(request.updated_at).toLocaleString()}
              </small>
            </div>
            <span
              className={`recruitment-status status-${request.status.toLowerCase()}`}
            >
              {statusLabel[request.status]}
            </span>
            <div className="quiz-actions">
              {request.status === "PENDING" && direction === "incoming" && (
                <>
                  <button
                    className="button button-primary"
                    disabled={busy !== null}
                    onClick={() => void act(request, "accept")}
                  >
                    {busy === request.id ? "Working…" : "Accept"}
                  </button>
                  <button
                    className="button button-secondary"
                    disabled={busy !== null}
                    onClick={() => void act(request, "decline")}
                  >
                    Decline
                  </button>
                </>
              )}
              {request.status === "PENDING" && direction === "outgoing" && (
                <button
                  className="button button-secondary"
                  disabled={busy !== null}
                  onClick={() => void act(request, "cancel")}
                >
                  {busy === request.id ? "Working…" : "Cancel"}
                </button>
              )}
              <button
                className="button button-secondary"
                disabled={busy !== null}
                onClick={() => void act(request, "block")}
              >
                Block
              </button>
            </div>
          </article>
        ))}
      </div>
    );
  }

  return (
    <section
      className="study-partner-section"
      aria-labelledby="partner-requests"
    >
      <div className="panel-heading">
        <div>
          <p className="eyebrow">REQUESTS</p>
          <h2 id="partner-requests">Study Partner requests</h2>
        </div>
      </div>
      <p className="field-hint">
        Blocking removes a student from discovery and cancels any pending
        request between you.
      </p>
      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="success-message" role="status">
          {message}
        </p>
      )}
      {loading ? (
        <p className="panel loading-state" role="status">
          Loading study requests…
        </p>
      ) : (
        <div className="study-partner-request-grid">
          <section className="panel">
            <h3>Incoming</h3>
            {requestRows({ items: incoming, direction: "incoming" })}
          </section>
          <section className="panel">
            <h3>Outgoing</h3>
            {requestRows({ items: outgoing, direction: "outgoing" })}
          </section>
        </div>
      )}
      {error && (
        <button className="button button-secondary" onClick={() => void load()}>
          Retry
        </button>
      )}
    </section>
  );
}

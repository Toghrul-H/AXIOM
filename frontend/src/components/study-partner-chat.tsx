"use client";

import {
  FormEvent,
  KeyboardEvent,
  ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  type StudyPartnerChat,
  type StudyPartnerMessage,
  studyPartnerApi,
} from "@/lib/study-partner";

const POLL_INTERVAL_MS = 5_000;
const MAX_MESSAGE_LENGTH = 2_000;

function mergeMessages(
  current: StudyPartnerMessage[],
  next: StudyPartnerMessage[],
) {
  const messages = new Map(current.map((message) => [message.id, message]));
  for (const message of next) messages.set(message.id, message);
  return [...messages.values()].sort(
    (first, second) =>
      first.created_at.localeCompare(second.created_at) || first.id - second.id,
  );
}

function safeMessageContent(content: string): ReactNode[] {
  return content.split(/(https?:\/\/[^\s<>"']+)/giu).map((part, index) => {
    if (!/^https?:\/\//iu.test(part)) return part;
    try {
      const url = new URL(part);
      if (url.protocol !== "http:" && url.protocol !== "https:") return part;
      return (
        <a
          href={url.href}
          key={`${url.href}-${index}`}
          rel="noopener noreferrer"
          target="_blank"
        >
          {part}
        </a>
      );
    } catch {
      return part;
    }
  });
}

function friendlyError(error: unknown, fallback: string) {
  if (!(error instanceof Error)) return fallback;
  if (
    /sign in|account unavailable|permission|conversation not available/i.test(
      error.message,
    )
  ) {
    return "This conversation is no longer available.";
  }
  return fallback;
}

export function StudyPartnerChat({ refreshKey }: { refreshKey: number }) {
  const [conversations, setConversations] = useState<StudyPartnerChat[]>([]);
  const [selectedRequestId, setSelectedRequestId] = useState<number | null>(
    null,
  );
  const [messages, setMessages] = useState<StudyPartnerMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [messageError, setMessageError] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const stickToBottomRef = useRef(true);
  const fetchingMessagesRef = useRef(false);
  const selectedRequestRef = useRef<number | null>(null);

  const loadConversations = useCallback(async () => {
    try {
      const next = await studyPartnerApi.chats();
      setConversations(next);
      setSelectedRequestId((current) => {
        if (current && next.some((chat) => chat.request_id === current))
          return current;
        return next[0]?.request_id ?? null;
      });
      setError("");
    } catch (loadError) {
      setError(friendlyError(loadError, "Conversations could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, []);

  const loadMessages = useCallback(async (requestId: number) => {
    if (fetchingMessagesRef.current) return;
    fetchingMessagesRef.current = true;
    const element = listRef.current;
    stickToBottomRef.current =
      !element ||
      element.scrollHeight - element.scrollTop - element.clientHeight < 80;
    try {
      const next = await studyPartnerApi.messages(requestId);
      if (selectedRequestRef.current === requestId) {
        setMessages((current) => mergeMessages(current, next));
        setMessageError("");
      }
    } catch (loadError) {
      if (selectedRequestRef.current === requestId) {
        setMessageError(
          friendlyError(loadError, "Messages could not be loaded."),
        );
      }
    } finally {
      fetchingMessagesRef.current = false;
      if (selectedRequestRef.current === requestId) setLoadingMessages(false);
    }
  }, []);

  useEffect(() => {
    const initial = window.setTimeout(() => void loadConversations(), 0);
    return () => window.clearTimeout(initial);
  }, [loadConversations, refreshKey]);

  useEffect(() => {
    selectedRequestRef.current = selectedRequestId;
    if (!selectedRequestId) return;
    const initial = window.setTimeout(() => {
      setMessages([]);
      setLoadingMessages(true);
      void loadMessages(selectedRequestId);
    }, 0);
    const polling = window.setInterval(() => {
      void loadMessages(selectedRequestId);
      void loadConversations();
    }, POLL_INTERVAL_MS);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(polling);
    };
  }, [loadConversations, loadMessages, selectedRequestId]);

  useEffect(() => {
    if (stickToBottomRef.current) {
      listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
    }
  }, [messages]);

  const selected = conversations.find(
    (chat) => chat.request_id === selectedRequestId,
  );

  async function send(event?: FormEvent) {
    event?.preventDefault();
    const content = draft.trim();
    if (!selectedRequestId || sending) return;
    if (!content) {
      setMessageError("Write a message before sending.");
      return;
    }
    if (content.length > MAX_MESSAGE_LENGTH) {
      setMessageError(
        `Messages can contain at most ${MAX_MESSAGE_LENGTH} characters.`,
      );
      return;
    }
    setSending(true);
    setMessageError("");
    stickToBottomRef.current = true;
    try {
      const message = await studyPartnerApi.sendMessage(
        selectedRequestId,
        content,
      );
      if (selectedRequestRef.current === selectedRequestId) {
        setMessages((current) => mergeMessages(current, [message]));
      }
      setDraft("");
      await loadConversations();
    } catch (sendError) {
      setMessageError(friendlyError(sendError, "Message could not be sent."));
    } finally {
      setSending(false);
    }
  }

  function onComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send();
    }
  }

  return (
    <section
      className="study-partner-section"
      aria-labelledby="study-partner-chat"
    >
      <div className="panel-heading">
        <div>
          <p className="eyebrow">CHAT</p>
          <h2 id="study-partner-chat">Messages</h2>
        </div>
      </div>
      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}
      {loading ? (
        <p className="panel loading-state" role="status">
          Loading conversations…
        </p>
      ) : conversations.length === 0 ? (
        <div className="panel empty-state">
          <h3>No active conversations</h3>
          <p>Accepted Study Partner connections appear here.</p>
          {error && (
            <button
              className="button button-secondary"
              onClick={() => void loadConversations()}
            >
              Retry
            </button>
          )}
        </div>
      ) : (
        <div className="study-partner-chat-layout">
          <nav
            aria-label="Study Partner conversations"
            className="study-partner-conversations"
          >
            {conversations.map((conversation) => (
              <button
                aria-current={
                  conversation.request_id === selectedRequestId
                    ? "page"
                    : undefined
                }
                className={`study-partner-conversation ${conversation.request_id === selectedRequestId ? "is-selected" : ""}`}
                key={conversation.request_id}
                onClick={() => {
                  selectedRequestRef.current = conversation.request_id;
                  setMessages([]);
                  setSelectedRequestId(conversation.request_id);
                }}
              >
                <strong>{conversation.counterpart.display_name}</strong>
                <span>
                  {conversation.last_message_preview ?? "Start a conversation"}
                </span>
              </button>
            ))}
          </nav>
          <div className="panel study-partner-message-panel">
            {selected ? (
              <>
                <h3>Chat with {selected.counterpart.display_name}</h3>
                {messageError && (
                  <p className="error-message" role="alert">
                    {messageError}
                  </p>
                )}
                <div
                  aria-live="polite"
                  className="study-partner-message-list"
                  ref={listRef}
                >
                  {loadingMessages ? (
                    <p className="loading-state" role="status">
                      Loading messages…
                    </p>
                  ) : messages.length === 0 ? (
                    <p className="empty-inline">No messages yet. Say hello.</p>
                  ) : (
                    messages.map((message) => {
                      const own =
                        message.sender_user_id !==
                        selected.counterpart.profile_id;
                      return (
                        <article
                          className={`study-partner-message ${own ? "is-own" : ""}`}
                          key={message.id}
                        >
                          <strong>
                            {own ? "You" : selected.counterpart.display_name}
                          </strong>
                          <p>{safeMessageContent(message.content)}</p>
                          <time dateTime={message.created_at}>
                            {new Date(message.created_at).toLocaleString()}
                          </time>
                        </article>
                      );
                    })
                  )}
                </div>
                <form
                  className="study-partner-composer"
                  onSubmit={(event) => void send(event)}
                >
                  <label htmlFor="study-partner-message">Message</label>
                  <textarea
                    id="study-partner-message"
                    maxLength={MAX_MESSAGE_LENGTH}
                    onChange={(event) => setDraft(event.target.value)}
                    onKeyDown={onComposerKeyDown}
                    placeholder="Write a message…"
                    value={draft}
                  />
                  <div className="quiz-actions">
                    <span className="field-hint">
                      Enter sends · Shift+Enter adds a line
                    </span>
                    <button
                      className="button button-primary"
                      disabled={sending || !draft.trim()}
                      type="submit"
                    >
                      {sending ? "Sending…" : "Send"}
                    </button>
                  </div>
                </form>
              </>
            ) : null}
          </div>
        </div>
      )}
      {!loading && error && conversations.length > 0 && (
        <button
          className="button button-secondary"
          onClick={() => void loadConversations()}
        >
          Retry
        </button>
      )}
    </section>
  );
}

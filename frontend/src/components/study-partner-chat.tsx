"use client";

import {
  ChangeEvent,
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
  type StudyPartnerMessageAttachment,
  type StudyPartnerMessage,
  type StudyPartnerReactionEmoji,
  STUDY_PARTNER_REACTION_EMOJIS,
  studyPartnerApi,
} from "@/lib/study-partner";

const POLL_INTERVAL_MS = 5_000;
const TYPING_THROTTLE_MS = 3_000;
const MAX_MESSAGE_LENGTH = 2_000;
const MAX_ATTACHMENT_BYTES = 5_000_000;
const MAX_ATTACHMENTS = 3;

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

function formatAttachmentSize(sizeBytes: number) {
  return sizeBytes < 1_000_000
    ? `${Math.max(1, Math.round(sizeBytes / 1_000))} KB`
    : `${(sizeBytes / 1_000_000).toFixed(1)} MB`;
}

export function StudyPartnerChat({ refreshKey }: { refreshKey: number }) {
  const [conversations, setConversations] = useState<StudyPartnerChat[]>([]);
  const [selectedRequestId, setSelectedRequestId] = useState<number | null>(
    null,
  );
  const [messages, setMessages] = useState<StudyPartnerMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [replyingTo, setReplyingTo] = useState<StudyPartnerMessage | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sending, setSending] = useState(false);
  const [uploadingIndex, setUploadingIndex] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [messageError, setMessageError] = useState("");
  const [reactingTo, setReactingTo] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const stickToBottomRef = useRef(true);
  const fetchingMessagesRef = useRef(false);
  const selectedRequestRef = useRef<number | null>(null);
  const lastReadMessageRef = useRef(new Map<number, number>());
  const lastTypingUpdateRef = useRef(0);
  const typingRequestRef = useRef<number | null>(null);

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

  const markRead = useCallback(
    async (requestId: number, messageId?: number) => {
      if (
        !messageId ||
        document.visibilityState !== "visible" ||
        !document.hasFocus()
      )
        return;
      if ((lastReadMessageRef.current.get(requestId) ?? 0) >= messageId) return;
      try {
        await studyPartnerApi.markRead(requestId, messageId);
        lastReadMessageRef.current.set(requestId, messageId);
        setConversations((current) =>
          current.map((conversation) =>
            conversation.request_id === requestId
              ? { ...conversation, unread_count: 0 }
              : conversation,
          ),
        );
      } catch {
        // Read status is retried on the next visible polling cycle.
      }
    },
    [],
  );

  const updateTyping = useCallback(
    async (requestId: number, isTyping: boolean) => {
      const timestamp = Date.now();
      if (
        isTyping &&
        typingRequestRef.current === requestId &&
        timestamp - lastTypingUpdateRef.current < TYPING_THROTTLE_MS
      )
        return;
      if (!isTyping && typingRequestRef.current !== requestId) return;
      try {
        await studyPartnerApi.typing(requestId, isTyping);
        typingRequestRef.current = isTyping ? requestId : null;
        lastTypingUpdateRef.current = isTyping ? timestamp : 0;
      } catch {
        // Typing is ephemeral; stale status naturally expires server-side.
      }
    },
    [],
  );

  const loadMessages = useCallback(
    async (requestId: number) => {
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
          void markRead(requestId, next.at(-1)?.id);
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
    },
    [markRead],
  );

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
    const requestId = selectedRequestId;
    return () => {
      if (requestId && typingRequestRef.current === requestId) {
        void updateTyping(requestId, false);
      }
    };
  }, [selectedRequestId, updateTyping]);

  useEffect(() => {
    function onVisibilityChange() {
      if (document.visibilityState !== "visible") return;
      const requestId = selectedRequestRef.current;
      if (requestId) void loadMessages(requestId);
      void loadConversations();
    }
    document.addEventListener("visibilitychange", onVisibilityChange);
    window.addEventListener("focus", onVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", onVisibilityChange);
      window.removeEventListener("focus", onVisibilityChange);
    };
  }, [loadConversations, loadMessages]);

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
    if (!content && selectedFiles.length === 0) {
      setMessageError("Write a message or attach a file before sending.");
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
    void updateTyping(selectedRequestId, false);
    const uploaded: StudyPartnerMessageAttachment[] = [];
    try {
      for (const [index, file] of selectedFiles.entries()) {
        setUploadingIndex(index);
        uploaded.push(
          await studyPartnerApi.uploadAttachment(selectedRequestId, file),
        );
      }
      const message = await studyPartnerApi.sendMessage(
        selectedRequestId,
        content,
        replyingTo?.id,
        uploaded.map((attachment) => attachment.id),
      );
      if (selectedRequestRef.current === selectedRequestId) {
        setMessages((current) => mergeMessages(current, [message]));
      }
      setDraft("");
      setSelectedFiles([]);
      setReplyingTo(null);
      await loadConversations();
    } catch (sendError) {
      await Promise.all(
        uploaded.map((attachment) =>
          studyPartnerApi
            .deleteAttachment(selectedRequestId, attachment.id)
            .catch(() => undefined),
        ),
      );
      setMessageError(friendlyError(sendError, "Message could not be sent."));
    } finally {
      setSending(false);
      setUploadingIndex(null);
    }
  }

  async function updateReaction(
    message: StudyPartnerMessage,
    emoji: StudyPartnerReactionEmoji,
  ) {
    if (!selectedRequestId) return;
    const reaction = (message.reactions ?? []).find(
      (candidate) => candidate.emoji === emoji,
    );
    const key = `${message.id}:${emoji}`;
    if (reactingTo) return;
    setReactingTo(key);
    setMessageError("");
    try {
      const next = reaction?.reacted_by_me
        ? await studyPartnerApi.removeReaction(
            selectedRequestId,
            message.id,
            emoji,
          )
        : await studyPartnerApi.addReaction(
            selectedRequestId,
            message.id,
            emoji,
          );
      if (selectedRequestRef.current === selectedRequestId) {
        setMessages((current) => mergeMessages(current, [next]));
      }
    } catch (reactionError) {
      setMessageError(
        friendlyError(reactionError, "Reaction could not be updated."),
      );
    } finally {
      setReactingTo(null);
    }
  }

  function showOriginal(messageId: number) {
    document
      .getElementById(`study-partner-message-${messageId}`)
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function onComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send();
    }
  }

  function onDraftChange(value: string) {
    setDraft(value);
    if (selectedRequestId) {
      void updateTyping(selectedRequestId, Boolean(value.trim()));
    }
  }

  function selectAttachments(event: ChangeEvent<HTMLInputElement>) {
    const incoming = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!incoming.length) return;
    if (selectedFiles.length + incoming.length > MAX_ATTACHMENTS) {
      setMessageError(`Attach up to ${MAX_ATTACHMENTS} files at once.`);
      return;
    }
    if (incoming.some((file) => file.size > MAX_ATTACHMENT_BYTES)) {
      setMessageError("Each attachment must be 5 MB or smaller.");
      return;
    }
    setMessageError("");
    setSelectedFiles((current) => [...current, ...incoming]);
  }

  function removeSelectedAttachment(index: number) {
    setSelectedFiles((current) => current.filter((_, item) => item !== index));
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
                  setReplyingTo(null);
                  setSelectedFiles([]);
                  setSelectedRequestId(conversation.request_id);
                }}
              >
                <strong>{conversation.counterpart.display_name}</strong>
                <span>
                  {conversation.last_message_preview ?? "Start a conversation"}
                </span>
                {conversation.unread_count > 0 && (
                  <b
                    aria-label={`${conversation.unread_count} unread messages`}
                    className="study-partner-unread-badge"
                  >
                    {conversation.unread_count > 99
                      ? "99+"
                      : conversation.unread_count}
                  </b>
                )}
              </button>
            ))}
          </nav>
          <div className="panel study-partner-message-panel">
            {selected ? (
              <>
                <div className="study-partner-chat-heading">
                  <h3>Chat with {selected.counterpart.display_name}</h3>
                  {selected.counterpart_typing && (
                    <span aria-live="polite" className="study-partner-typing">
                      {selected.counterpart.display_name} is typing…
                    </span>
                  )}
                </div>
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
                      const reactions = message.reactions ?? [];
                      const own =
                        message.sender_user_id !==
                        selected.counterpart.profile_id;
                      return (
                        <article
                          className={`study-partner-message ${own ? "is-own" : ""}`}
                          id={`study-partner-message-${message.id}`}
                          key={message.id}
                        >
                          <strong>
                            {own ? "You" : selected.counterpart.display_name}
                          </strong>
                          {message.reply_to && (
                            <button
                              className="study-partner-reply-quote"
                              onClick={() => showOriginal(message.reply_to!.id)}
                              type="button"
                            >
                              <span>
                                {message.reply_to.sender_user_id ===
                                selected.counterpart.profile_id
                                  ? selected.counterpart.display_name
                                  : "You"}
                              </span>
                              {message.reply_to.content}
                            </button>
                          )}
                          <p>{safeMessageContent(message.content)}</p>
                          {message.attachments?.length > 0 && (
                            <ul className="study-partner-attachments">
                              {message.attachments.map((attachment) => {
                                const base = `/api/study-partner/chats/${selected.request_id}/attachments/${attachment.id}`;
                                return (
                                  <li key={attachment.id}>
                                    <div>
                                      <strong>{attachment.filename}</strong>
                                      <span>
                                        {attachment.media_type} ·{" "}
                                        {formatAttachmentSize(
                                          attachment.size_bytes,
                                        )}
                                      </span>
                                    </div>
                                    <div className="study-partner-attachment-actions">
                                      {attachment.is_inline_preview && (
                                        <a
                                          href={`${base}/preview`}
                                          rel="noopener noreferrer"
                                          target="_blank"
                                        >
                                          View
                                        </a>
                                      )}
                                      <a href={`${base}/download`}>Download</a>
                                    </div>
                                  </li>
                                );
                              })}
                            </ul>
                          )}
                          <time dateTime={message.created_at}>
                            {new Date(message.created_at).toLocaleString()}
                          </time>
                          {own && (
                            <span
                              aria-label={
                                message.seen_by_counterpart
                                  ? "Seen by your study partner"
                                  : "Sent to your study partner"
                              }
                              className="study-partner-receipt"
                            >
                              {message.seen_by_counterpart ? "Seen" : "Sent"}
                            </span>
                          )}
                          <div
                            aria-label="Message actions"
                            className="study-partner-message-actions"
                          >
                            <div
                              aria-label="Add or remove a reaction"
                              className="study-partner-reactions"
                            >
                              {STUDY_PARTNER_REACTION_EMOJIS.map((emoji) => {
                                const reaction = reactions.find(
                                  (candidate) => candidate.emoji === emoji,
                                );
                                const reactionKey = `${message.id}:${emoji}`;
                                return (
                                  <button
                                    aria-label={`${reaction?.reacted_by_me ? "Remove" : "Add"} ${emoji} reaction`}
                                    aria-pressed={
                                      reaction?.reacted_by_me ?? false
                                    }
                                    className={`study-partner-reaction ${reaction?.reacted_by_me ? "is-active" : ""}`}
                                    disabled={reactingTo !== null}
                                    key={emoji}
                                    onClick={() =>
                                      void updateReaction(message, emoji)
                                    }
                                    type="button"
                                  >
                                    {emoji}
                                    {reaction ? (
                                      <span>{reaction.count}</span>
                                    ) : null}
                                    {reactingTo === reactionKey ? (
                                      <span className="sr-only">Updating</span>
                                    ) : null}
                                  </button>
                                );
                              })}
                            </div>
                            <button
                              className="button button-secondary study-partner-reply-action"
                              onClick={() => setReplyingTo(message)}
                              type="button"
                            >
                              Reply
                            </button>
                          </div>
                        </article>
                      );
                    })
                  )}
                </div>
                <form
                  className="study-partner-composer"
                  onSubmit={(event) => void send(event)}
                >
                  {replyingTo && (
                    <div className="study-partner-composer-reply">
                      <div>
                        <strong>Replying to message</strong>
                        <span>{replyingTo.content}</span>
                      </div>
                      <button
                        aria-label="Cancel reply"
                        className="button button-secondary"
                        onClick={() => setReplyingTo(null)}
                        type="button"
                      >
                        Cancel reply
                      </button>
                    </div>
                  )}
                  {selectedFiles.length > 0 && (
                    <ul className="study-partner-selected-attachments">
                      {selectedFiles.map((file, index) => (
                        <li key={`${file.name}-${file.lastModified}-${index}`}>
                          <div>
                            <strong>{file.name}</strong>
                            <span>{formatAttachmentSize(file.size)}</span>
                          </div>
                          <button
                            aria-label={`Remove ${file.name}`}
                            className="button button-secondary"
                            disabled={sending}
                            onClick={() => removeSelectedAttachment(index)}
                            type="button"
                          >
                            Remove
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                  <label htmlFor="study-partner-message">Message</label>
                  <textarea
                    id="study-partner-message"
                    maxLength={MAX_MESSAGE_LENGTH}
                    onBlur={() => {
                      if (selectedRequestId)
                        void updateTyping(selectedRequestId, false);
                    }}
                    onChange={(event) => onDraftChange(event.target.value)}
                    onKeyDown={onComposerKeyDown}
                    placeholder="Write a message…"
                    value={draft}
                  />
                  <div className="quiz-actions">
                    <span className="field-hint">
                      Enter sends · Shift+Enter adds a line · Files up to 5 MB
                    </span>
                    <label className="button button-secondary study-partner-attach">
                      Attach file
                      <input
                        accept=".pdf,.png,.jpg,.jpeg,.webp,.txt,.md,.markdown"
                        disabled={
                          sending || selectedFiles.length >= MAX_ATTACHMENTS
                        }
                        onChange={selectAttachments}
                        type="file"
                      />
                    </label>
                    <button
                      className="button button-primary"
                      disabled={
                        sending || (!draft.trim() && !selectedFiles.length)
                      }
                      type="submit"
                    >
                      {sending
                        ? uploadingIndex !== null
                          ? `Uploading ${uploadingIndex + 1} of ${selectedFiles.length}…`
                          : "Sending…"
                        : "Send"}
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

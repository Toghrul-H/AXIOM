import { apiFetch, AuthRequestError, authRequest } from "./auth";

export type StudyFormat = "ONLINE" | "IN_PERSON" | "EITHER";
export type TopicPurpose = "WANT_TO_STUDY" | "CAN_HELP";
export type StudyPartnerRequestStatus =
  "PENDING" | "ACCEPTED" | "DECLINED" | "CANCELLED";

export type StudyPartnerTopic = {
  topic_id: number;
  purpose: TopicPurpose;
  name: string;
  slug: string;
};

export type AvailabilitySlot = {
  weekday: number;
  start_minute: number;
  end_minute: number;
};

export type StudyPartnerProfile = {
  exists: boolean;
  display_name: string | null;
  is_participating: boolean;
  is_discoverable: boolean;
  study_format: StudyFormat;
  introduction: string | null;
  topics: StudyPartnerTopic[];
  availability: AvailabilitySlot[];
};

export type StudyPartnerProfileWrite = Omit<
  StudyPartnerProfile,
  "exists" | "display_name" | "topics"
> & {
  display_name: string;
  topics: Pick<StudyPartnerTopic, "topic_id" | "purpose">[];
};

export type StudyPartnerPublicProfile = {
  profile_id: number;
  display_name: string;
  introduction: string | null;
  study_format: StudyFormat;
  shared_study_topics: StudyPartnerTopic[];
  complementary_topics: StudyPartnerTopic[];
  has_compatible_availability: boolean;
};

export type StudyPartnerRequest = {
  id: number;
  status: StudyPartnerRequestStatus;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  counterpart: { profile_id: number; display_name: string };
};

export type StudyPartnerChat = {
  request_id: number;
  counterpart: { profile_id: number; display_name: string };
  last_message_preview: string | null;
  last_message_at: string | null;
  unread_count: number;
  counterpart_typing: boolean;
};

export type StudyPartnerMessage = {
  id: number;
  sender_user_id: number;
  content: string;
  created_at: string;
  reply_to_message_id: number | null;
  reply_to: {
    id: number;
    sender_user_id: number;
    content: string;
  } | null;
  reactions: StudyPartnerMessageReaction[];
  seen_by_counterpart: boolean;
  attachments: StudyPartnerMessageAttachment[];
};

export const STUDY_PARTNER_REACTION_EMOJIS = [
  "👍",
  "❤️",
  "😂",
  "😮",
  "😢",
  "🎉",
] as const;

export type StudyPartnerReactionEmoji =
  (typeof STUDY_PARTNER_REACTION_EMOJIS)[number];

export type StudyPartnerMessageReaction = {
  emoji: StudyPartnerReactionEmoji;
  count: number;
  reacted_by_me: boolean;
};

export type StudyPartnerMessageAttachment = {
  id: number;
  filename: string;
  media_type: string;
  size_bytes: number;
  is_inline_preview: boolean;
};

export type PartnerFilters = {
  topicIds?: number[];
  studyFormat?: StudyFormat;
};

export const studyPartnerApi = {
  mine: () => authRequest<StudyPartnerProfile>("/study-partner/me"),
  save: (profile: StudyPartnerProfileWrite) =>
    authRequest<StudyPartnerProfile>("/study-partner/me", "PUT", profile),
  partners: ({ topicIds = [], studyFormat }: PartnerFilters = {}) => {
    const query = new URLSearchParams();
    for (const topicId of topicIds) query.append("topic_id", String(topicId));
    if (studyFormat) query.set("study_format", studyFormat);
    const suffix = query.toString();
    return authRequest<StudyPartnerPublicProfile[]>(
      `/study-partner/partners${suffix ? `?${suffix}` : ""}`,
    );
  },
  sendRequest: (recipient_profile_id: number) =>
    authRequest<StudyPartnerRequest>("/study-partner/requests", "POST", {
      recipient_profile_id,
    }),
  requests: (
    direction: "incoming" | "outgoing",
    requestStatus?: StudyPartnerRequestStatus,
  ) => {
    const query = new URLSearchParams({ direction });
    if (requestStatus) query.set("request_status", requestStatus);
    return authRequest<StudyPartnerRequest[]>(
      `/study-partner/requests?${query}`,
    );
  },
  accept: (requestId: number) =>
    authRequest<StudyPartnerRequest>(
      `/study-partner/requests/${requestId}/accept`,
      "POST",
    ),
  decline: (requestId: number) =>
    authRequest<StudyPartnerRequest>(
      `/study-partner/requests/${requestId}/decline`,
      "POST",
    ),
  cancel: (requestId: number) =>
    authRequest<StudyPartnerRequest>(
      `/study-partner/requests/${requestId}/cancel`,
      "POST",
    ),
  block: (blocked_user_id: number) =>
    authRequest("/study-partner/blocks", "POST", { blocked_user_id }),
  unblock: (userId: number) =>
    authRequest<void>(`/study-partner/blocks/${userId}`, "DELETE"),
  chats: () => authRequest<StudyPartnerChat[]>("/study-partner/chats"),
  messages: (requestId: number, offset = 0, limit = 100) =>
    authRequest<StudyPartnerMessage[]>(
      `/study-partner/chats/${requestId}/messages?offset=${offset}&limit=${limit}`,
    ),
  markRead: (requestId: number, last_message_id: number) =>
    authRequest<{ last_read_message_id: number | null }>(
      `/study-partner/chats/${requestId}/read`,
      "POST",
      { last_message_id },
    ),
  typing: (requestId: number, is_typing: boolean) =>
    authRequest<{ is_typing: boolean }>(
      `/study-partner/chats/${requestId}/typing`,
      "POST",
      { is_typing },
    ),
  sendMessage: (
    requestId: number,
    content: string,
    reply_to_message_id?: number,
    attachment_ids: number[] = [],
  ) =>
    authRequest<StudyPartnerMessage>(
      `/study-partner/chats/${requestId}/messages`,
      "POST",
      {
        content,
        ...(reply_to_message_id ? { reply_to_message_id } : {}),
        ...(attachment_ids.length ? { attachment_ids } : {}),
      },
    ),
  uploadAttachment: async (requestId: number, file: File) => {
    const response = await apiFetch(
      `/study-partner/chats/${requestId}/attachments`,
      {
        method: "POST",
        body: file,
        headers: {
          "Content-Type": file.type || "application/octet-stream",
          "X-Chat-Filename": file.name,
        },
      },
    );
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new AuthRequestError(
        response.status,
        typeof data?.detail === "string"
          ? data.detail
          : "Attachment upload failed.",
      );
    }
    return response.json() as Promise<StudyPartnerMessageAttachment>;
  },
  deleteAttachment: (requestId: number, attachmentId: number) =>
    authRequest<void>(
      `/study-partner/chats/${requestId}/attachments/${attachmentId}`,
      "DELETE",
    ),
  addReaction: (
    requestId: number,
    messageId: number,
    emoji: StudyPartnerReactionEmoji,
  ) =>
    authRequest<StudyPartnerMessage>(
      `/study-partner/chats/${requestId}/messages/${messageId}/reactions`,
      "POST",
      { emoji },
    ),
  removeReaction: (
    requestId: number,
    messageId: number,
    emoji: StudyPartnerReactionEmoji,
  ) =>
    authRequest<StudyPartnerMessage>(
      `/study-partner/chats/${requestId}/messages/${messageId}/reactions`,
      "DELETE",
      { emoji },
    ),
};

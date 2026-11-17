import { authRequest } from "./auth";

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
};

export type StudyPartnerMessage = {
  id: number;
  sender_user_id: number;
  content: string;
  created_at: string;
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
  sendMessage: (requestId: number, content: string) =>
    authRequest<StudyPartnerMessage>(
      `/study-partner/chats/${requestId}/messages`,
      "POST",
      { content },
    ),
};

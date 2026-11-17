import { authRequest } from "./auth";

export type StudyFormat = "ONLINE" | "IN_PERSON" | "EITHER";
export type TopicPurpose = "WANT_TO_STUDY" | "CAN_HELP";

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

export const studyPartnerApi = {
  mine: () => authRequest<StudyPartnerProfile>("/study-partner/me"),
  save: (profile: StudyPartnerProfileWrite) =>
    authRequest<StudyPartnerProfile>("/study-partner/me", "PUT", profile),
};

"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import { PageHeading } from "@/components/page-heading";
import {
  StudyPartnerDiscovery,
  StudyPartnerRequests,
} from "@/components/study-partner-community";
import { questionsApi, type Topic } from "@/lib/questions";
import {
  type AvailabilitySlot,
  type StudyFormat,
  type StudyPartnerProfile,
  type StudyPartnerProfileWrite,
  studyPartnerApi,
} from "@/lib/study-partner";

type SlotDraft = AvailabilitySlot & { key: string };
type ProfileDraft = Omit<StudyPartnerProfileWrite, "availability"> & {
  availability: SlotDraft[];
};

const weekdays = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

const blank = (): ProfileDraft => ({
  display_name: "",
  is_participating: false,
  is_discoverable: false,
  study_format: "EITHER",
  introduction: null,
  topics: [],
  availability: [],
});

function slotFromApi(slot: AvailabilitySlot, index: number): SlotDraft {
  return {
    ...slot,
    key: `saved-${index}-${slot.weekday}-${slot.start_minute}`,
  };
}

function draftFrom(profile: StudyPartnerProfile): ProfileDraft {
  return {
    display_name: profile.display_name ?? "",
    is_participating: profile.is_participating,
    is_discoverable: profile.is_discoverable,
    study_format: profile.study_format,
    introduction: profile.introduction,
    topics: profile.topics.map(({ topic_id, purpose }) => ({
      topic_id,
      purpose,
    })),
    availability: profile.availability.map(slotFromApi),
  };
}

function minutesToTime(minutes: number) {
  const hours = Math.floor(minutes / 60);
  return `${String(hours).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;
}

function timeToMinutes(value: string) {
  const [hours, minutes] = value.split(":").map(Number);
  return Number.isInteger(hours) && Number.isInteger(minutes)
    ? hours * 60 + minutes
    : 0;
}

function clientValidation(form: ProfileDraft) {
  const errors: Record<string, string> = {};
  if (form.display_name.trim().length < 2)
    errors.display_name = "Enter a display name with at least two characters.";
  if (form.display_name.length > 60)
    errors.display_name = "Display names may contain at most 60 characters.";
  const preferences = form.topics.map(
    (item) => `${item.topic_id}:${item.purpose}`,
  );
  if (new Set(preferences).size !== preferences.length)
    errors.topics = "Each topic can be selected once for each purpose.";
  if (form.availability.length > 28)
    errors.availability = "You can add up to 28 availability slots.";
  const slots = [...form.availability].sort(
    (left, right) =>
      left.weekday - right.weekday || left.start_minute - right.start_minute,
  );
  if (
    slots.some(
      (slot, index) =>
        slot.start_minute >= slot.end_minute ||
        (index > 0 &&
          slots[index - 1].weekday === slot.weekday &&
          slot.start_minute < slots[index - 1].end_minute),
    )
  )
    errors.availability =
      "Availability slots must not overlap and must end after they start.";
  return errors;
}

export function StudyPartnerProfileEditor() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [form, setForm] = useState<ProfileDraft>(blank);
  const [loadedParticipating, setLoadedParticipating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [activityVersion, setActivityVersion] = useState(0);
  const slotCounter = useRef(0);

  async function load() {
    await Promise.resolve();
    setLoading(true);
    setError("");
    try {
      const [profile, metadata] = await Promise.all([
        studyPartnerApi.mine(),
        questionsApi.metadata(),
      ]);
      setTopics(metadata.topics);
      setForm(draftFrom(profile));
      setLoadedParticipating(profile.is_participating);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Study Partner profile could not be loaded.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, []);

  function toggleTopic(topicId: number, purpose: "WANT_TO_STUDY" | "CAN_HELP") {
    setForm((current) => {
      const exists = current.topics.some(
        (item) => item.topic_id === topicId && item.purpose === purpose,
      );
      return {
        ...current,
        topics: exists
          ? current.topics.filter(
              (item) => item.topic_id !== topicId || item.purpose !== purpose,
            )
          : [...current.topics, { topic_id: topicId, purpose }],
      };
    });
  }

  function updateSlot(key: string, changes: Partial<SlotDraft>) {
    setForm((current) => ({
      ...current,
      availability: current.availability.map((slot) =>
        slot.key === key ? { ...slot, ...changes } : slot,
      ),
    }));
  }

  function addSlot() {
    setForm((current) => {
      if (current.availability.length >= 28) return current;
      return {
        ...current,
        availability: [
          ...current.availability,
          {
            key: `new-${slotCounter.current++}`,
            weekday: 0,
            start_minute: 540,
            end_minute: 600,
          },
        ],
      };
    });
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors = clientValidation(form);
    setErrors(nextErrors);
    setMessage("");
    setError("");
    if (Object.keys(nextErrors).length || saving) return;
    if (
      loadedParticipating &&
      !form.is_participating &&
      !window.confirm(
        "Pausing your profile will cancel any pending Study Partner requests. Continue?",
      )
    )
      return;
    setSaving(true);
    try {
      const payload: StudyPartnerProfileWrite = {
        ...form,
        display_name: form.display_name.trim(),
        introduction: form.introduction?.trim() || null,
        availability: form.availability.map((slot) => ({
          weekday: slot.weekday,
          start_minute: slot.start_minute,
          end_minute: slot.end_minute,
        })),
      };
      const saved = await studyPartnerApi.save(payload);
      setForm(draftFrom(saved));
      setLoadedParticipating(saved.is_participating);
      setErrors({});
      setError("");
      setMessage(
        saved.is_participating
          ? saved.is_discoverable
            ? "Your Study Partner profile is visible to other participating students."
            : "Your profile is saved but hidden from partner discovery."
          : "Your Study Partner profile is paused. Pending requests were cancelled.",
      );
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? saveError.message
          : "Your Study Partner profile could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  }

  const selected = (topicId: number, purpose: "WANT_TO_STUDY" | "CAN_HELP") =>
    form.topics.some(
      (item) => item.topic_id === topicId && item.purpose === purpose,
    );

  return (
    <>
      <PageHeading
        eyebrow="STUDENT COMMUNITY"
        title="Study Partner"
        description="Create an opt-in profile for finding a compatible Discrete Mathematics I study partner."
      />
      {loading ? (
        <p className="panel loading-state" role="status">
          Loading your Study Partner profile…
        </p>
      ) : error && !topics.length ? (
        <section className="panel empty-state" role="alert">
          <h2>Study Partner is unavailable</h2>
          <p>{error}</p>
          <button
            className="button button-secondary"
            onClick={() => void load()}
          >
            Retry
          </button>
        </section>
      ) : (
        <>
          <form className="panel study-partner-form" onSubmit={submit}>
            <div className="panel-heading">
              <div>
                <p className="eyebrow">YOUR PROFILE</p>
                <h2>Choose what other students can see</h2>
              </div>
            </div>
            <p className="study-partner-privacy">
              Your email, Neptun code, and exact availability are never shown in
              partner discovery. Only your display name, introduction, study
              format, and selected topics may be visible when you opt in.
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

            <fieldset>
              <legend>Participation</legend>
              <label className="study-partner-toggle">
                <input
                  type="checkbox"
                  checked={form.is_participating}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      is_participating: event.target.checked,
                      is_discoverable: event.target.checked
                        ? current.is_discoverable
                        : false,
                    }))
                  }
                />
                Participate in Study Partner
              </label>
              <label className="study-partner-toggle">
                <input
                  type="checkbox"
                  disabled={!form.is_participating}
                  checked={form.is_discoverable}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      is_discoverable: event.target.checked,
                    }))
                  }
                />
                Make my profile discoverable
              </label>
              {!form.is_participating && loadedParticipating && (
                <p className="field-hint">
                  Saving a paused profile cancels pending Study Partner
                  requests.
                </p>
              )}
            </fieldset>

            <fieldset disabled={saving}>
              <legend>Public profile</legend>
              <label>
                Display name
                <input
                  aria-invalid={Boolean(errors.display_name)}
                  minLength={2}
                  maxLength={60}
                  required
                  value={form.display_name}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      display_name: event.target.value,
                    }))
                  }
                />
              </label>
              {errors.display_name && (
                <span className="field-error">{errors.display_name}</span>
              )}
              <label>
                Study format
                <select
                  value={form.study_format}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      study_format: event.target.value as StudyFormat,
                    }))
                  }
                >
                  <option value="EITHER">Online or in person</option>
                  <option value="ONLINE">Online</option>
                  <option value="IN_PERSON">In person</option>
                </select>
              </label>
              <label>
                Short introduction{" "}
                <span className="field-hint">(optional)</span>
                <textarea
                  maxLength={500}
                  value={form.introduction ?? ""}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      introduction: event.target.value || null,
                    }))
                  }
                />
              </label>
            </fieldset>

            <fieldset disabled={saving}>
              <legend>Topics</legend>
              <p className="field-hint">
                Select separately what you want to study and what you can help
                with.
              </p>
              <div className="study-partner-topic-grid">
                <section aria-labelledby="want-to-study-heading">
                  <h3 id="want-to-study-heading">I want to study</h3>
                  {topics.map((topic) => (
                    <label key={`want-${topic.id}`}>
                      <input
                        type="checkbox"
                        checked={selected(topic.id, "WANT_TO_STUDY")}
                        onChange={() => toggleTopic(topic.id, "WANT_TO_STUDY")}
                      />{" "}
                      {topic.name}
                    </label>
                  ))}
                </section>
                <section aria-labelledby="can-help-heading">
                  <h3 id="can-help-heading">I can help with</h3>
                  {topics.map((topic) => (
                    <label key={`help-${topic.id}`}>
                      <input
                        type="checkbox"
                        checked={selected(topic.id, "CAN_HELP")}
                        onChange={() => toggleTopic(topic.id, "CAN_HELP")}
                      />{" "}
                      {topic.name}
                    </label>
                  ))}
                </section>
              </div>
              {errors.topics && (
                <span className="field-error">{errors.topics}</span>
              )}
            </fieldset>

            <fieldset disabled={saving}>
              <legend>Weekly availability</legend>
              <p className="field-hint">
                This helps calculate compatibility but is not shown to other
                students.
              </p>
              <div className="study-partner-slots">
                {form.availability.map((slot) => (
                  <div className="study-partner-slot" key={slot.key}>
                    <label>
                      Day
                      <select
                        value={slot.weekday}
                        onChange={(event) =>
                          updateSlot(slot.key, {
                            weekday: Number(event.target.value),
                          })
                        }
                      >
                        {weekdays.map((day, index) => (
                          <option key={day} value={index}>
                            {day}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      From
                      <input
                        type="time"
                        value={minutesToTime(slot.start_minute)}
                        onChange={(event) =>
                          updateSlot(slot.key, {
                            start_minute: timeToMinutes(event.target.value),
                          })
                        }
                      />
                    </label>
                    <label>
                      Until
                      <input
                        type="time"
                        disabled={slot.end_minute === 1440}
                        value={
                          slot.end_minute === 1440
                            ? ""
                            : minutesToTime(slot.end_minute)
                        }
                        onChange={(event) =>
                          updateSlot(slot.key, {
                            end_minute: timeToMinutes(event.target.value),
                          })
                        }
                      />
                    </label>
                    <label className="study-partner-midnight">
                      <input
                        type="checkbox"
                        checked={slot.end_minute === 1440}
                        onChange={(event) =>
                          updateSlot(slot.key, {
                            end_minute: event.target.checked
                              ? 1440
                              : Math.min(1439, slot.start_minute + 60),
                          })
                        }
                      />{" "}
                      End at midnight
                    </label>
                    <button
                      type="button"
                      className="button button-secondary"
                      onClick={() =>
                        setForm((current) => ({
                          ...current,
                          availability: current.availability.filter(
                            (item) => item.key !== slot.key,
                          ),
                        }))
                      }
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
              {errors.availability && (
                <span className="field-error">{errors.availability}</span>
              )}
              <button
                type="button"
                className="button button-secondary"
                onClick={addSlot}
                disabled={form.availability.length >= 28 || saving}
              >
                Add availability
              </button>
            </fieldset>

            <div className="quiz-actions">
              <button className="button button-primary" disabled={saving}>
                {saving ? "Saving profile…" : "Save profile"}
              </button>
            </div>
          </form>
          <StudyPartnerDiscovery
            topics={topics}
            enabled={loadedParticipating}
            refreshKey={activityVersion}
            onActivity={() => setActivityVersion((current) => current + 1)}
          />
          <StudyPartnerRequests
            refreshKey={activityVersion}
            onActivity={() => setActivityVersion((current) => current + 1)}
          />
        </>
      )}
    </>
  );
}

"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "./auth-provider";
import { PageHeading } from "./page-heading";
import { documentSections, formValues } from "@/lib/document-preview";
import { DocumentWorkspace } from "./document-preview";
import {
  policyLabels,
  policyTextFields,
  policyNumberFields,
  rulesTextFields,
  policyInput,
  rulesInput,
  type Policy,
  type Rules,
  type PolicyCode,
  type SubmissionDeadline,
  assessmentRequest,
  canManageAssessments,
  eventInput,
  roomRowsInput,
  saveRoomRows,
  eventLabels,
  roomEventTypes,
  type Semester,
  type Detail,
  type AssessmentEvent,
  type EventType,
  type Room,
} from "@/lib/assessments";

export function AssessmentAccess({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  return canManageAssessments(user?.role) ? (
    children
  ) : (
    <p role="alert">Access denied.</p>
  );
}

function EditForm({
  children,
  save,
  remove,
  label,
  fresh = false,
  previewScope,
}: {
  children: React.ReactNode;
  save: (data: FormData) => Promise<void>;
  remove?: () => Promise<void>;
  label: string;
  fresh?: boolean;
  previewScope?: string;
}) {
  const [busy, setBusy] = useState(false),
    [dirty, setDirty] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const lock = useRef(false);
  const formRef = useRef<HTMLFormElement>(null);
  // Compare committed input values with the initial/last successful save snapshot.
  useEffect(() => {
    const form = formRef.current;
    if (!form || busy) return;
    const current = formValues(new FormData(form));
    form.dataset.savedValues ??= current;
    setDirty(current !== form.dataset.savedValues);
  }, [busy, children]);
  useEffect(() => {
    if (!dirty && !busy) return;
    const unload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    const navigate = (e: MouseEvent) => {
      if (
        e.target instanceof Element &&
        e.target.closest("a[href]") &&
        !window.confirm("Leave this page? Unsaved changes may be lost.")
      ) {
        e.preventDefault();
        e.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", unload);
    document.addEventListener("click", navigate, true);
    return () => {
      window.removeEventListener("beforeunload", unload);
      document.removeEventListener("click", navigate, true);
    };
  }, [dirty, busy]);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (lock.current) return;
    const form = e.currentTarget;
    const submitted = new FormData(form);
    lock.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await save(submitted);
      form.dataset.savedValues = formValues(submitted);
      setDirty(false);
      setNotice("Saved.");
      if (fresh) {
        form.reset();
        delete form.dataset.savedValues;
      }
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Could not save. Please retry.",
      );
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  async function destroy() {
    if (
      !remove ||
      lock.current ||
      !window.confirm(
        `Delete ${label}? Its saved contents will be removed, including any room assignments. Unsaved changes here will be discarded.`,
      )
    )
      return;
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      await remove();
      setDirty(false);
      setNotice("Deleted.");
    } catch (error) {
      setError(error instanceof Error ? error.message : "Could not delete.");
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  return (
    <form
      ref={formRef}
      className="auth-form assessment-form"
      data-preview-scope={previewScope}
      data-dirty={dirty}
      onSubmit={submit}
      onClick={(e) => {
        if (
          e.target instanceof Element &&
          e.target.closest("[data-assessment-change]")
        ) {
          setDirty(true);
          setNotice("");
        }
      }}
      onChange={(e) => {
        setDirty(
          formValues(new FormData(e.currentTarget)) !==
            e.currentTarget.dataset.savedValues,
        );
        setNotice("");
      }}
    >
      <fieldset disabled={busy}>
        {children}
        <div className="staff-actions">
          {dirty && (
            <span className="field-hint">Unsaved changes in this section</span>
          )}
          <button className="button button-primary">
            {busy ? "Saving…" : `Save ${label}`}
          </button>
          {remove && (
            <button
              className="button button-secondary"
              type="button"
              onClick={destroy}
            >
              Delete {label}
            </button>
          )}
        </div>
      </fieldset>
      {error && (
        <p role="alert" className="error-message">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
    </form>
  );
}
function MetadataFields({ value }: { value?: Semester }) {
  return (
    <>
      <label>
        Academic year starting
        <input
          name="academic_year_start"
          type="number"
          min={1900}
          max={9998}
          required
          defaultValue={value?.academic_year_start ?? new Date().getFullYear()}
        />
      </label>
      <p className="field-hint">
        The starting year identifies the academic year, for example 2026 means
        2026/27.
      </p>
      <label>
        Term
        <select name="term" defaultValue={value?.term ?? "FALL"}>
          <option value="FALL">Fall</option>
          <option value="SPRING">Spring</option>
        </select>
      </label>
      <label>
        Display label
        <input
          name="display_label"
          required
          maxLength={200}
          defaultValue={value?.display_label ?? ""}
        />
      </label>
    </>
  );
}
function metadata(form: FormData) {
  return {
    academic_year_start: Number(form.get("academic_year_start")),
    term: form.get("term"),
    display_label: String(form.get("display_label")).trim(),
  };
}

export function AssessmentList() {
  const router = useRouter();
  const [rows, setRows] = useState<Semester[] | null>(null),
    [error, setError] = useState(""),
    [offset, setOffset] = useState(0),
    [revision, setRevision] = useState(0),
    [notice, setNotice] = useState("");
  const deleting = useRef(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const abort = new AbortController();
    assessmentRequest<Semester[]>(
      `?offset=${offset}&limit=20`,
      "GET",
      undefined,
      abort.signal,
    )
      .then(setRows)
      .catch((e) => {
        if (!abort.signal.aborted) setError(e.message);
      });
    return () => abort.abort();
  }, [offset, revision]);
  function reload(next = offset) {
    setRows(null);
    setError("");
    setOffset(next);
    setRevision((n) => n + 1);
  }
  async function remove(row: Semester) {
    if (
      deleting.current ||
      !window.confirm(
        `Delete ${row.display_label} and all its assessments and room assignments?`,
      )
    )
      return;
    deleting.current = true;
    setBusy(true);
    try {
      await assessmentRequest(`/${row.id}`, "DELETE");
      setNotice("Semester configuration deleted.");
      reload(rows?.length === 1 ? Math.max(0, offset - 20) : offset);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Deletion failed.");
    } finally {
      deleting.current = false;
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="TEACHING WORKSPACE"
        title="Assessment Documents"
        description="Manage semester dates, times, venues and practice group room assignments."
      />
      <section className="panel quiz-panel">
        <h2>Semester configurations</h2>
        {error && (
          <p role="alert">
            {error}{" "}
            <button
              onClick={() => reload()}
              className="button button-secondary"
            >
              Retry
            </button>
          </p>
        )}
        {notice && <p role="status">{notice}</p>}
        {!rows && !error && <p role="status">Loading semesters…</p>}
        {rows?.length === 0 && (
          <p>
            No semester configurations yet. Create one to store the dates,
            times, venues and room assignments used by assessment documents.
          </p>
        )}
        {rows?.map((row) => (
          <article className="staff-row" key={row.id}>
            <div>
              <h3>{row.display_label}</h3>
              <p>
                {row.academic_year_start}/
                {String(row.academic_year_start + 1).slice(-2)} ·{" "}
                {row.term === "FALL" ? "Fall" : "Spring"}
              </p>
              <p>Updated {new Date(row.updated_at).toLocaleDateString()}</p>
            </div>
            <div className="staff-actions">
              <Link
                className="button button-primary"
                href={`/teacher/assessments/${row.id}`}
              >
                Open / Edit
              </Link>
              <button
                className="button button-secondary"
                disabled={busy}
                onClick={() => remove(row)}
              >
                Delete
              </button>
            </div>
          </article>
        ))}
        <div className="staff-actions">
          <button
            className="button button-secondary"
            disabled={!rows || offset === 0}
            onClick={() => reload(Math.max(0, offset - 20))}
          >
            Previous
          </button>
          <button
            className="button button-secondary"
            disabled={!rows || rows.length < 20}
            onClick={() => reload(offset + 20)}
          >
            Next
          </button>
        </div>
      </section>
      <section className="panel quiz-panel">
        <h2>Create semester configuration</h2>
        <EditForm
          label="semester"
          save={async (form) => {
            const saved = await assessmentRequest<Detail>(
              "",
              "POST",
              metadata(form),
            );
            router.push(`/teacher/assessments/${saved.id}`);
          }}
        >
          <MetadataFields />
        </EditForm>
      </section>
    </>
  );
}

function EventEditor({
  type,
  value,
  base,
  update,
}: {
  type: EventType;
  value?: AssessmentEvent;
  base: string;
  update: (
    change: (previous?: AssessmentEvent) => AssessmentEvent | undefined,
  ) => void;
}) {
  const path = `${base}/events`;
  return (
    <section className="panel quiz-panel">
      <h2>{eventLabels[type]} — Schedule &amp; Logistics</h2>
      <EditForm
        key={value?.id ?? "new"}
        previewScope={`event:${type}`}
        label={eventLabels[type]}
        save={async (form) => {
          const saved = await assessmentRequest<AssessmentEvent>(
            value ? `${path}/${value.id}` : path,
            value ? "PUT" : "POST",
            eventInput(form, type),
          );
          update((previous) => ({
            ...saved,
            rooms: previous?.rooms ?? saved.rooms,
          }));
        }}
        remove={
          value
            ? async () => {
                await assessmentRequest(`${path}/${value.id}`, "DELETE");
                update(() => undefined);
              }
            : undefined
        }
      >
        <div className="assessment-fields">
          {(
            [
              ["date", "Date", "date"],
              ["start_time", "Scheduled start time", "time"],
              ["end_time", "Scheduled end time", "time"],
              ["writing_start_time", "Actual writing start time", "time"],
              ["writing_end_time", "Actual writing end time", "time"],
              ["venue", "Venue", "text"],
              ["document_date", "Document date", "date"],
              ["latest_arrival_time", "Latest arrival time", "time"],
            ] as const
          ).map(([name, label, kind]) => (
            <label key={name}>
              {label}
              <input
                name={name}
                title={
                  kind === "time"
                    ? "Scheduled: official interval. Writing: actual test time."
                    : undefined
                }
                type={kind}
                step={kind === "time" ? "any" : undefined}
                maxLength={kind === "text" ? 200 : undefined}
                defaultValue={value?.[name] ?? ""}
              />
            </label>
          ))}
        </div>
        <details className="document-advanced">
          <summary>Instructions &amp; Configuration (optional)</summary>
          <label>
            Seating plan (optional; describe rows, columns or arrangements by
            retake type)
            <textarea
              name="seating_plan"
              maxLength={20000}
              defaultValue={value?.seating_plan ?? ""}
            />
          </label>
          <label>
            Notes (optional)
            <textarea
              name="notes"
              maxLength={20000}
              defaultValue={value?.notes ?? ""}
            />
          </label>
        </details>
        {(type === "COURSEWORK_HAND_IN" ||
          type === "COURSEWORK_RETAKE_HAND_IN") && (
          <SubmissionFields value={value} />
        )}
      </EditForm>
      {roomEventTypes.includes(type) &&
        (value ? (
          <Rooms
            event={value}
            path={`${path}/${value.id}/rooms`}
            update={(change) =>
              update((previous) =>
                previous
                  ? { ...previous, rooms: change(previous.rooms) }
                  : previous,
              )
            }
          />
        ) : (
          <p>
            Room assignments are optional. Save this assessment before assigning
            rooms.
          </p>
        ))}
    </section>
  );
}
function Rooms({
  event,
  path,
  update,
}: {
  event: AssessmentEvent;
  path: string;
  update: (change: (rooms: Room[]) => Room[]) => void;
}) {
  const [rows, setRows] = useState<
    { key: string; room: string; groups: string }[]
  >(() =>
    event.rooms.map((room) => ({
      key: `saved-${room.id}`,
      room: room.room,
      groups: room.groups.map((g) => g.identifier).join(", "),
    })),
  );
  const next = useRef(0);
  const saved = useRef(
    new Map(event.rooms.map((room) => [`saved-${room.id}`, room])),
  );
  return (
    <section>
      <h3>Room assignments</h3>
      <EditForm
        label="room assignments"
        previewScope={`rooms:${event.event_type}`}
        save={async (form) => {
          const values = roomRowsInput(form);
          await saveRoomRows(path, values, saved.current, (rooms) =>
            update(() => rooms),
          );
        }}
      >
        {rows.map((row, index) => (
          <div className="room-assignment-row" key={row.key}>
            <input type="hidden" name="room_key" value={row.key} />
            <label>
              Room
              <input
                name={`room_${row.key}`}
                maxLength={200}
                value={row.room}
                onChange={(e) => {
                  const value = e.target.value;
                  setRows((current) =>
                    current.map((r) =>
                      r.key === row.key ? { ...r, room: value } : r,
                    ),
                  );
                }}
              />
            </label>
            <label>
              Practice groups
              <input
                name={`groups_${row.key}`}
                value={row.groups}
                onChange={(e) => {
                  const value = e.target.value;
                  setRows((current) =>
                    current.map((r) =>
                      r.key === row.key ? { ...r, groups: value } : r,
                    ),
                  );
                }}
              />
            </label>
            <button
              type="button"
              className="button button-secondary"
              data-assessment-change
              aria-label={`Remove room row ${index + 1}`}
              onClick={() =>
                setRows((current) => current.filter((r) => r.key !== row.key))
              }
            >
              Remove
            </button>
          </div>
        ))}
        <button
          type="button"
          className="button button-secondary"
          data-assessment-change
          onClick={() => {
            // Allocate once per click, outside the replayable React state updater.
            const key = `draft-${next.current++}`;
            setRows((current) => [...current, { key, room: "", groups: "" }]);
          }}
        >
          + Add room
        </button>
      </EditForm>
    </section>
  );
}

export function AssessmentDetail({ id }: { id: string }) {
  const [data, setData] = useState<Detail | null>(null),
    [error, setError] = useState(""),
    [revision, setRevision] = useState(0);
  useEffect(() => {
    const abort = new AbortController();
    assessmentRequest<Detail>(`/${id}`, "GET", undefined, abort.signal)
      .then(setData)
      .catch((e) => {
        if (!abort.signal.aborted) setError(e.message);
      });
    return () => abort.abort();
  }, [id, revision]);
  if (!data)
    return error ? (
      <p role="alert">
        {error}{" "}
        <button
          className="button button-secondary"
          onClick={() => {
            setError("");
            setRevision((n) => n + 1);
          }}
        >
          Retry
        </button>
      </p>
    ) : (
      <p role="status">Loading semester…</p>
    );
  function eventEditor(type: EventType) {
    return (
      <EventEditor
        type={type}
        value={data!.events.find((e) => e.event_type === type)}
        base={`/${id}`}
        update={(change) =>
          setData((current) => {
            if (!current) return current;
            const value = change(
              current.events.find((e) => e.event_type === type),
            );
            return {
              ...current,
              events: [
                ...current.events.filter((e) => e.event_type !== type),
                ...(value ? [value] : []),
              ],
            };
          })
        }
      />
    );
  }
  return (
    <>
      <Link href="/teacher/assessments">Back to Assessment Documents</Link>
      <PageHeading
        eyebrow="ASSESSMENT DOCUMENTS"
        title={data.display_label}
        description={`${data.academic_year_start}/${String(data.academic_year_start + 1).slice(-2)} · ${data.term === "FALL" ? "Fall" : "Spring"}`}
      />
      <DocumentWorkspace id={id}>
        {(kind) => {
          const visible = documentSections(kind);
          return (
            <>
              <details className="panel quiz-panel">
                <summary>Edit semester details</summary>
                <EditForm
                  previewScope="metadata"
                  label="semester"
                  save={async (form) => {
                    const saved = await assessmentRequest<Detail>(
                      `/${id}`,
                      "PATCH",
                      metadata(form),
                    );
                    setData((current) =>
                      current
                        ? { ...current, ...saved, events: current.events }
                        : saved,
                    );
                  }}
                >
                  <MetadataFields value={data} />
                </EditForm>
              </details>
              <div hidden={!visible.rules}>
                <SemesterRules base={`/${id}`} plusOnly={visible.plusOnly} />
              </div>
              {(
                [
                  "MIDTERM",
                  "ENDTERM",
                  "SHORT_QUIZZES",
                  "COURSEWORK",
                ] as PolicyCode[]
              ).map((code) => {
                const types = (Object.keys(eventLabels) as EventType[]).filter(
                  (type) =>
                    code === "COURSEWORK"
                      ? type.startsWith("COURSEWORK_")
                      : code === "SHORT_QUIZZES"
                        ? type === "SHORT_QUIZ_RETAKE"
                        : type === code,
                );
                return (
                  <details
                    open={
                      kind !== "DATES_OF_ASSESSMENTS" &&
                      kind !== "RULES_OF_ASSESSMENT"
                    }
                    key={code}
                    hidden={
                      !visible.policy(code) && !types.some(visible.events)
                    }
                    className="document-config-section"
                  >
                    <summary>{policyLabels[code]}</summary>
                    {types.map((type) => (
                      <div key={type} hidden={!visible.events(type)}>
                        {eventEditor(type)}
                      </div>
                    ))}
                    <div hidden={!visible.policy(code)}>
                      <h3>Assessment &amp; Scoring</h3>
                      <PolicyEditor
                        code={code}
                        value={data.policies?.find((p) => p.code === code)}
                        base={`/${id}`}
                        update={(saved) =>
                          setData((current) =>
                            current
                              ? {
                                  ...current,
                                  policies: [
                                    ...(current.policies ?? []).filter(
                                      (p) => p.code !== code,
                                    ),
                                    saved,
                                  ],
                                }
                              : current,
                          )
                        }
                      />
                    </div>
                  </details>
                );
              })}
              <div hidden={!visible.events("TEST_RETAKE")}>
                {eventEditor("TEST_RETAKE")}
              </div>
            </>
          );
        }}
      </DocumentWorkspace>
    </>
  );
}

function PolicyEditor({
  code,
  value,
  base,
  update,
}: {
  code: PolicyCode;
  value?: Policy;
  base: string;
  update: (value: Policy) => void;
}) {
  return (
    <EditForm
      previewScope={`policy:${code}`}
      label={policyLabels[code]}
      save={async (form) =>
        update(
          await assessmentRequest<Policy>(
            `${base}/policies/${code}`,
            "PUT",
            policyInput(form),
          ),
        )
      }
    >
      <div className="assessment-fields">
        {(
          Object.entries(policyNumberFields) as [
            keyof typeof policyNumberFields,
            string,
          ][]
        ).map(([name, label]) => (
          <label key={name}>
            {label}
            <input
              name={name}
              type="number"
              min={
                name === "duration_minutes" || name === "assessment_count"
                  ? 1
                  : 0
              }
              max={
                name === "duration_minutes"
                  ? 10080
                  : name === "assessment_count"
                    ? 1000
                    : 100000
              }
              step={
                name === "duration_minutes" || name === "assessment_count"
                  ? 1
                  : "0.01"
              }
              defaultValue={value?.[name] ?? ""}
            />
          </label>
        ))}
      </div>
      {(
        Object.entries(policyTextFields).filter(
          ([name]) =>
            ![
              "retake_rules",
              "preparation_instructions",
              "conduct_instructions",
            ].includes(name),
        ) as [keyof typeof policyTextFields, string][]
      ).map(([name, label]) => (
        <label key={name}>
          {label}
          <textarea
            name={name}
            maxLength={20000}
            defaultValue={value?.[name] ?? ""}
          />
        </label>
      ))}
      <details className="document-advanced">
        <summary>Additional instructions and retake rules</summary>{" "}
        {(
          Object.entries(policyTextFields).filter(([name]) =>
            [
              "retake_rules",
              "preparation_instructions",
              "conduct_instructions",
            ].includes(name),
          ) as [keyof typeof policyTextFields, string][]
        ).map(([name, label]) => (
          <label key={name}>
            {label}
            <textarea
              name={name}
              maxLength={20000}
              defaultValue={value?.[name] ?? ""}
            />
          </label>
        ))}
      </details>{" "}
    </EditForm>
  );
}
function SemesterRules({
  base,
  plusOnly = false,
}: {
  base: string;
  plusOnly?: boolean;
}) {
  const [rules, setRules] = useState<Rules | null>(null),
    [error, setError] = useState(""),
    [revision, setRevision] = useState(0);
  useEffect(() => {
    const abort = new AbortController();
    assessmentRequest<Rules>(`${base}/rules`, "GET", undefined, abort.signal)
      .then(setRules)
      .catch((e) => {
        if (!abort.signal.aborted) setError(e.message);
      });
    return () => abort.abort();
  }, [base, revision]);
  return (
    <section className="panel quiz-panel">
      <h2>
        {plusOnly
          ? "Plus points rules and limits"
          : "Semester scoring and academic rules"}
      </h2>
      {!rules ? (
        error ? (
          <p role="alert">
            {error}{" "}
            <button
              type="button"
              className="button button-secondary"
              onClick={() => {
                setError("");
                setRevision((n) => n + 1);
              }}
            >
              Retry
            </button>
          </p>
        ) : (
          <p role="status">Loading rules...</p>
        )
      ) : (
        <>
          <p>
            All fields are optional. Describe plus-point tasks, fractional
            awards, deadlines, eligibility and exceptional policies here. No
            rules are inferred from earlier semesters.
          </p>
          <EditForm
            previewScope="rules"
            label="semester rules"
            save={async (form) =>
              setRules(
                await assessmentRequest<Rules>(
                  `${base}/rules`,
                  "PUT",
                  rulesInput(form),
                ),
              )
            }
          >
            {(
              Object.entries(rulesTextFields) as [
                keyof typeof rulesTextFields,
                string,
              ][]
            ).map(([name, label]) => (
              <label
                key={name}
                hidden={
                  plusOnly &&
                  name !== "plus_points_rules" &&
                  name !== "total_score_rules"
                }
              >
                {label}
                <textarea
                  name={name}
                  maxLength={20000}
                  defaultValue={rules[name] ?? ""}
                />
              </label>
            ))}
            <label>
              Maximum plus points
              <input
                name="plus_points_maximum"
                type="number"
                min={0}
                max={100000}
                step="0.01"
                defaultValue={rules.plus_points_maximum ?? ""}
              />
            </label>
            <div hidden={plusOnly}>
              <h3>Grade minimum scores</h3>
              <p>
                Enter all five thresholds, starting grade 1 at zero, or leave
                all empty. Each grade extends up to the next threshold
                (exclusive). Course-passing conditions remain separate.
              </p>
              <div className="assessment-fields">
                {[1, 2, 3, 4, 5].map((grade) => (
                  <label key={grade}>
                    Grade {grade}
                    <input
                      name={`grade_${grade}`}
                      type="number"
                      min={0}
                      max={100000}
                      step="0.01"
                      defaultValue={
                        rules.grade_boundaries.find((b) => b.grade === grade)
                          ?.minimum_score ?? ""
                      }
                    />
                  </label>
                ))}
              </div>
            </div>{" "}
          </EditForm>
        </>
      )}
    </section>
  );
}
function SubmissionFields({ value }: { value?: AssessmentEvent }) {
  const [rows, setRows] = useState<
    { key: number; value?: SubmissionDeadline }[]
  >(() =>
    (value?.group_deadlines ?? []).map((row, key) => ({ key, value: row })),
  );
  const next = useRef(rows.length);
  return (
    <section>
      <h3>Submission deadline and venue</h3>
      <p>
        These fields are separate from the scheduled interval. Group entries
        override the general submission details; empty fields inherit the
        general value. Use instructions for relative deadlines such as the
        penultimate class.
      </p>
      <div className="assessment-fields">
        {(
          [
            ["submission_deadline_date", "General deadline date", "date"],
            ["submission_deadline_time", "General deadline time", "time"],
            ["submission_venue", "Submission venue", "text"],
          ] as const
        ).map(([name, label, type]) => (
          <label key={name}>
            {label}
            <input
              name={name}
              type={type}
              step={type === "time" ? "any" : undefined}
              maxLength={200}
              defaultValue={value?.[name] ?? ""}
            />
          </label>
        ))}
      </div>
      <label>
        Submission instructions
        <textarea
          name="submission_instructions"
          maxLength={20000}
          defaultValue={value?.submission_instructions ?? ""}
        />
      </label>
      <h4>Group-specific deadlines</h4>
      {rows.map((row) => (
        <div className="panel" key={row.key}>
          {(
            [
              ["group_identifier", "group", "Practice group", "text"],
              ["deadline_date", "date", "Deadline date", "date"],
              ["deadline_time", "time", "Deadline time", "time"],
              ["venue", "venue", "Submission venue", "text"],
            ] as const
          ).map(([field, name, label, type]) => (
            <label key={field}>
              {label}
              <input
                name={`deadline_${name}_${row.key}`}
                type={type}
                required={field === "group_identifier"}
                step={type === "time" ? "any" : undefined}
                maxLength={field === "group_identifier" ? 50 : 200}
                defaultValue={row.value?.[field] ?? ""}
              />
            </label>
          ))}
          <label>
            Instructions
            <textarea
              name={`deadline_instructions_${row.key}`}
              maxLength={20000}
              defaultValue={row.value?.instructions ?? ""}
            />
          </label>
          <button
            type="button"
            className="button button-secondary"
            data-assessment-change
            onClick={() => setRows(rows.filter((r) => r.key !== row.key))}
          >
            Remove group deadline
          </button>
        </div>
      ))}
      <button
        type="button"
        className="button button-secondary"
        data-assessment-change
        onClick={() => setRows([...rows, { key: next.current++ }])}
      >
        Add group deadline
      </button>
    </section>
  );
}

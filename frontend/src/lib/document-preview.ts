import {
  eventInput,
  policyInput,
  roomInput,
  roomRowsInput,
  rulesInput,
  type EventType,
} from "./assessments";

export const documentLabels = {
  DATES_OF_ASSESSMENTS: "Dates of Assessments",
  ENDTERM_TEST_INFORMATION: "Endterm Test Information",
  RULES_OF_ASSESSMENT: "Rules of Assessment",
  RULES_OF_EARNING_PLUS_POINTS: "Plus Points Rules",
  MIDTERM_TEST_INFORMATION: "Midterm Test Information",
  TEST_RETAKE_INFORMATION: "Midterm/Endterm Retake Information",
  COURSEWORK_ASSIGNMENT_INFORMATION: "Coursework Assignment Information",
} as const;
export type DocumentType = keyof typeof documentLabels;
// Visibility only: keep canonical forms mounted to preserve unsaved shared values.
export function documentSections(kind: DocumentType) {
  const dates = kind === "DATES_OF_ASSESSMENTS",
    rules = kind === "RULES_OF_ASSESSMENT",
    retake = kind === "TEST_RETAKE_INFORMATION";
  return {
    rules: rules || kind === "RULES_OF_EARNING_PLUS_POINTS",
    plusOnly: kind === "RULES_OF_EARNING_PLUS_POINTS",
    events: (type: EventType) =>
      dates ||
      rules ||
      (kind === "COURSEWORK_ASSIGNMENT_INFORMATION" &&
        type.startsWith("COURSEWORK_")) ||
      (retake && type === "TEST_RETAKE") ||
      (kind === "MIDTERM_TEST_INFORMATION" && type === "MIDTERM") ||
      (kind === "ENDTERM_TEST_INFORMATION" && type === "ENDTERM"),
    policy: (code: string) =>
      dates ||
      rules ||
      (kind === "COURSEWORK_ASSIGNMENT_INFORMATION" && code === "COURSEWORK") ||
      (retake && (code === "MIDTERM" || code === "ENDTERM")) ||
      (kind === "MIDTERM_TEST_INFORMATION" && code === "MIDTERM") ||
      (kind === "ENDTERM_TEST_INFORMATION" && code === "ENDTERM"),
  };
}
export type PreviewNode = {
  kind: string;
  text?: string;
  children?: PreviewNode[];
  level?: number;
  ordered?: boolean;
};
export type Preview = { blocks: PreviewNode[]; label: string };
export type FormSnapshot = { scope: string; values: FormData; dirty: boolean };

export function formValues(data: FormData) {
  return JSON.stringify(Array.from(data.entries()));
}

export function hasUnsavedDocumentChanges(
  element: HTMLElement,
  kind: DocumentType,
) {
  const sections = documentSections(kind);
  return Array.from(
    element.querySelectorAll<HTMLFormElement>("form[data-preview-scope]"),
  ).some((form) => {
    const [scope, code] = form.dataset.previewScope!.split(":");
    const relevant =
      scope === "metadata" ||
      (scope === "rules" && sections.rules) ||
      (scope === "policy" && sections.policy(code)) ||
      ((scope === "event" || scope === "rooms") &&
        sections.events(code as EventType));
    return (
      relevant &&
      (Boolean(form.querySelector("fieldset:disabled")) ||
        form.dataset.savedValues !== formValues(new FormData(form)))
    );
  });
}

// Snapshot current DOM values: defaultValue and saved React state may be older.
export function draftFromForms(forms: FormSnapshot[]) {
  const meta = forms.find((f) => f.scope === "metadata")?.values;
  if (!meta) throw new Error("The editor is still loading.");
  const events = forms
    .filter((f) => f.scope.startsWith("event:"))
    .map((f) => {
      const type = f.scope.slice(6) as EventType;
      const batch = forms.find((r) => r.scope === `rooms:${type}`);
      const rooms = batch
        ? roomRowsInput(batch.values).map(({ room, groups }) => ({
            room,
            groups,
          }))
        : forms
            .filter((r) => r.scope.startsWith(`room:${type}:`))
            .flatMap((r) => {
              if (
                r.scope.endsWith(":new") &&
                !String(r.values.get("room") ?? "").trim() &&
                !String(r.values.get("groups") ?? "").trim()
              )
                return [];
              return [roomInput(r.values)];
            });
      return { ...eventInput(f.values, type), rooms };
    });
  const rules = forms.find((f) => f.scope === "rules");
  return {
    metadata: {
      academic_year_start: Number(meta.get("academic_year_start")),
      term: meta.get("term"),
      display_label: String(meta.get("display_label") ?? "").trim(),
    },
    events,
    policies: forms
      .filter((f) => f.scope.startsWith("policy:"))
      .map((f) => ({ code: f.scope.slice(7), ...policyInput(f.values) })),
    ...(rules ? { rules: rulesInput(rules.values) } : {}),
  };
}

// Cancelling at edit time (rather than after debounce) prevents an older response
// from being displayed as the current draft while the lecturer is still typing.
export function previewScheduler<T>(
  read: () => T,
  send: (draft: T, signal: AbortSignal) => Promise<Preview>,
  changed: (state: {
    loading: boolean;
    error: string;
    preview?: Preview;
  }) => void,
  delay = 350,
) {
  let timer: ReturnType<typeof setTimeout> | undefined;
  let abort: AbortController | undefined;
  let version = 0;
  return {
    schedule() {
      const current = ++version;
      clearTimeout(timer);
      abort?.abort();
      changed({ loading: true, error: "" });
      timer = setTimeout(async () => {
        abort = new AbortController();
        try {
          const preview = await send(read(), abort.signal);
          if (current === version)
            changed({ loading: false, error: "", preview });
        } catch (error) {
          if (current === version)
            changed({
              loading: false,
              error:
                error instanceof Error
                  ? error.message
                  : "Preview could not be loaded.",
            });
        }
      }, delay);
    },
    dispose() {
      version++;
      clearTimeout(timer);
      abort?.abort();
    },
  };
}

export function snapshotEditor(element: HTMLElement) {
  const forms = Array.from(
    element.querySelectorAll<HTMLFormElement>("form[data-preview-scope]"),
  );
  if (forms.some((form) => form.querySelector("fieldset:disabled")))
    throw new Error("Wait for saving to finish before generating a document.");
  return draftFromForms(
    forms.map((form) => ({
      scope: form.dataset.previewScope!,
      values: new FormData(form),
      dirty: form.dataset.dirty === "true",
    })),
  );
}

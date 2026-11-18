"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Download, Eye, Plus, Save, Trash2 } from "lucide-react";

import {
  courseApi,
  materialFile,
  type CourseMaterial,
  type CourseMaterialPublic,
} from "@/lib/course";

type Parent = {
  chapterId?: number;
  lessonId?: number;
  label: string;
  published: boolean;
};

const bytes = (value: number) =>
  value < 1024 * 1024
    ? `${Math.ceil(value / 1024)} KB`
    : `${(value / (1024 * 1024)).toFixed(1)} MB`;
const previewable = (type: string) =>
  type === "application/pdf" ||
  type.startsWith("image/") ||
  type.startsWith("text/");

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function PublicMaterials({
  materials,
  label,
}: {
  materials: CourseMaterialPublic[];
  label: string;
}) {
  const [error, setError] = useState("");
  const [loadingId, setLoadingId] = useState<number | null>(null);
  const [preview, setPreview] = useState<{
    name: string;
    type: string;
    url: string;
    text?: string;
  } | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const restoreFocus = useRef<HTMLElement | null>(null);

  useEffect(
    () => () => {
      if (preview?.url) URL.revokeObjectURL(preview.url);
    },
    [preview],
  );
  useEffect(() => {
    if (preview && dialog.current && !dialog.current.open)
      dialog.current.showModal();
    if (!preview && dialog.current?.open) dialog.current.close();
  }, [preview]);
  if (!materials.length) return null;
  const load = async (
    material: CourseMaterialPublic,
    action: "download" | "preview",
  ) => {
    if (loadingId !== null) return;
    setLoadingId(material.id);
    setError("");
    try {
      const file = await materialFile(material.id, action);
      if (action === "download") return saveBlob(file.blob, file.filename);
      const url = URL.createObjectURL(file.blob);
      const text = file.mediaType.startsWith("text/")
        ? await file.blob.text()
        : undefined;
      restoreFocus.current = document.activeElement as HTMLElement | null;
      setPreview((current) => {
        if (current?.url) URL.revokeObjectURL(current.url);
        return { name: file.filename, type: file.mediaType, url, text };
      });
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Material is unavailable.",
      );
    } finally {
      setLoadingId(null);
    }
  };
  return (
    <section className="course-materials" aria-label={`${label} materials`}>
      <h2>Materials</h2>
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
      <ul>
        {materials.map((material) => (
          <li key={material.id} className="course-material-row">
            <div>
              <strong>{material.title}</strong>
              {material.description && <p>{material.description}</p>}
              <small>
                {material.filename} · {material.media_type} ·{" "}
                {bytes(material.size_bytes)}
              </small>
            </div>
            <div className="course-actions">
              {previewable(material.media_type) && (
                <button
                  className="button button-quiet"
                  disabled={loadingId !== null}
                  onClick={() => void load(material, "preview")}
                >
                  <Eye size={16} />
                  Preview
                </button>
              )}
              <button
                className="button button-quiet"
                disabled={loadingId !== null}
                onClick={() => void load(material, "download")}
              >
                <Download size={16} />
                Download
              </button>
            </div>
          </li>
        ))}
      </ul>
      {preview && (
        <dialog
          ref={dialog}
          className="course-material-preview"
          aria-label={`Preview ${preview.name}`}
          onCancel={(event) => {
            event.preventDefault();
            setPreview(null);
          }}
          onClose={() =>
            window.setTimeout(() => restoreFocus.current?.focus(), 0)
          }
        >
          <header>
            <strong>{preview.name}</strong>
            <button
              className="button button-quiet"
              onClick={() => setPreview(null)}
            >
              Close
            </button>
          </header>
          {preview.text !== undefined ? (
            <pre>{preview.text}</pre>
          ) : preview.type.startsWith("image/") ? (
            <>
              <span className="sr-only">Image preview</span>
              {/* Authenticated Blob URLs cannot use Next image optimization. */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={preview.url} alt={`Preview of ${preview.name}`} />
            </>
          ) : (
            <iframe
              src={preview.url}
              title={`Preview of ${preview.name}`}
              sandbox=""
            />
          )}
        </dialog>
      )}
    </section>
  );
}

export function MaterialManager({
  parent,
  materials,
  busy,
  onRun,
}: {
  parent: Parent;
  materials: CourseMaterial[];
  busy: boolean;
  onRun: (
    action: () => Promise<unknown>,
    success: string,
    reloadOnError?: boolean,
  ) => Promise<void>;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const ordered = useMemo(
    () => [...materials].sort((a, b) => a.position - b.position || a.id - b.id),
    [materials],
  );
  const add = (event: FormEvent) => {
    event.preventDefault();
    if (!file || busy) return;
    void onRun(
      async () => {
        const created = await courseApi.createMaterial({
          title,
          description: description || null,
          position: ordered.length,
          ...(parent.chapterId
            ? { chapter_id: parent.chapterId }
            : { lesson_id: parent.lessonId }),
        });
        return courseApi.uploadMaterial(created.id, file);
      },
      "Material uploaded as draft.",
      true,
    ).then(() => {
      setTitle("");
      setDescription("");
      setFile(null);
    });
  };
  const reorder = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= ordered.length) return;
    const ids = ordered.map((item) => item.id);
    [ids[index], ids[target]] = [ids[target], ids[index]];
    void onRun(
      () => courseApi.reorderMaterials(parent, ids),
      "Material order saved.",
    );
  };
  return (
    <section className="course-material-manager">
      <h3>Materials for {parent.label}</h3>
      <form onSubmit={add} className="course-material-form">
        <label>
          Title
          <input
            required
            value={title}
            onChange={(event) => setTitle(event.target.value)}
          />
        </label>
        <label>
          Description
          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
        </label>
        <label>
          File
          <input
            required
            type="file"
            accept=".pdf,.ppt,.pptx,.doc,.docx,.png,.jpg,.jpeg,.webp,.txt,.md,.markdown"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </label>
        <p className="muted small">
          PDF, Office, images, UTF-8 text, or Markdown. ZIP and executable files
          are not accepted.
        </p>
        <button className="button button-primary" disabled={busy || !file}>
          <Plus size={16} />
          Upload draft material
        </button>
        {busy && <p role="status">Uploading material…</p>}
      </form>
      {!ordered.length ? (
        <p className="muted">No materials yet.</p>
      ) : (
        <ul className="course-material-list">
          {ordered.map((material, index) => (
            <ManagedMaterial
              key={material.id}
              material={material}
              parent={parent}
              index={index}
              count={ordered.length}
              busy={busy}
              onRun={onRun}
              move={() => reorder(index, -1)}
              moveDown={() => reorder(index, 1)}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

function ManagedMaterial({
  material,
  parent,
  index,
  count,
  busy,
  onRun,
  move,
  moveDown,
}: {
  material: CourseMaterial;
  parent: Parent;
  index: number;
  count: number;
  busy: boolean;
  onRun: (
    action: () => Promise<unknown>,
    success: string,
    reloadOnError?: boolean,
  ) => Promise<void>;
  move: () => void;
  moveDown: () => void;
}) {
  const [title, setTitle] = useState(material.title);
  const [description, setDescription] = useState(material.description ?? "");
  const [file, setFile] = useState<File | null>(null);
  return (
    <li className="course-material-row">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void onRun(
            () =>
              courseApi.updateMaterial(material.id, {
                title,
                description: description || null,
              }),
            "Material details saved.",
          );
        }}
      >
        <div>
          <span className={`exam-status ${material.status}`}>
            {material.status}
          </span>
          <label>
            Title
            <input
              required
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
          </label>
          <label>
            Description
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </label>
          {material.storage_ready ? (
            <small>
              {material.filename} · {material.media_type} ·{" "}
              {bytes(material.size_bytes ?? 0)}
            </small>
          ) : (
            <>
              <small className="field-error">No verified file uploaded.</small>
              <label>
                File
                <input
                  type="file"
                  accept=".pdf,.ppt,.pptx,.doc,.docx,.png,.jpg,.jpeg,.webp,.txt,.md,.markdown"
                  onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                />
              </label>
            </>
          )}
        </div>
        <div className="course-actions">
          <button className="button button-quiet" disabled={busy}>
            <Save size={16} />
            Save
          </button>
          {!material.storage_ready && (
            <button
              type="button"
              className="button button-primary"
              disabled={busy || !file}
              onClick={() =>
                file &&
                void onRun(
                  () => courseApi.uploadMaterial(material.id, file),
                  "Material file uploaded.",
                  true,
                )
              }
            >
              Upload file
            </button>
          )}
          <button
            type="button"
            className="button button-quiet"
            disabled={busy || index === 0}
            onClick={move}
          >
            Move up
          </button>
          <button
            type="button"
            className="button button-quiet"
            disabled={busy || index === count - 1}
            onClick={moveDown}
          >
            Move down
          </button>
          <button
            type="button"
            className="button button-quiet"
            disabled={
              busy ||
              !material.storage_ready ||
              (!parent.published && material.status !== "published")
            }
            onClick={() =>
              void onRun(
                () =>
                  courseApi.publishMaterial(
                    material.id,
                    material.status !== "published",
                  ),
                material.status === "published"
                  ? "Material returned to draft."
                  : "Material published.",
              )
            }
          >
            {material.status === "published" ? "Unpublish" : "Publish"}
          </button>
          <button
            type="button"
            className="button button-danger"
            disabled={busy}
            onClick={() => {
              if (window.confirm(`Delete “${material.title}”?`))
                void onRun(
                  () => courseApi.deleteMaterial(material.id),
                  "Material deleted.",
                );
            }}
          >
            <Trash2 size={16} />
            Delete
          </button>
        </div>
      </form>
    </li>
  );
}

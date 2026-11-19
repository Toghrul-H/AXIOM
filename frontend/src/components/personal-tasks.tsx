"use client";

import { FormEvent, useState } from "react";

import {
  personalTasksApi,
  type PersonalTask,
  type PersonalTaskWrite,
} from "@/lib/personal-tasks";

const emptyTask: PersonalTaskWrite = {
  title: "",
  due_date: null,
  completed: false,
};

export function PersonalTasks({
  tasks,
  onChange,
}: {
  tasks: PersonalTask[] | null;
  onChange: (tasks: PersonalTask[]) => void;
}) {
  const [draft, setDraft] = useState<PersonalTaskWrite>(emptyTask);
  const [editing, setEditing] = useState<PersonalTask | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (pending || !draft.title.trim()) return;
    setPending(true);
    setError("");
    try {
      const saved = editing
        ? await personalTasksApi.update(editing.id, draft)
        : await personalTasksApi.create(draft);
      const next = editing
        ? (tasks ?? []).map((task) => (task.id === saved.id ? saved : task))
        : [...(tasks ?? []), saved];
      onChange(next);
      setDraft(emptyTask);
      setEditing(null);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Task could not be saved.",
      );
    } finally {
      setPending(false);
    }
  };

  const toggle = async (task: PersonalTask) => {
    if (pending) return;
    setPending(true);
    setError("");
    try {
      const saved = await personalTasksApi.update(task.id, {
        title: task.title,
        due_date: task.due_date,
        completed: !task.completed,
      });
      onChange(
        (tasks ?? []).map((item) => (item.id === saved.id ? saved : item)),
      );
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Task could not be updated.",
      );
    } finally {
      setPending(false);
    }
  };

  const remove = async (task: PersonalTask) => {
    if (pending || !window.confirm(`Delete “${task.title}”?`)) return;
    setPending(true);
    setError("");
    try {
      await personalTasksApi.remove(task.id);
      onChange((tasks ?? []).filter((item) => item.id !== task.id));
      if (editing?.id === task.id) setEditing(null);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Task could not be deleted.",
      );
    } finally {
      setPending(false);
    }
  };

  const beginEdit = (task: PersonalTask) => {
    setEditing(task);
    setDraft({
      title: task.title,
      due_date: task.due_date,
      completed: task.completed,
    });
  };

  return (
    <section className="panel personal-tasks" id="personal-tasks">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">PERSONAL</p>
          <h2>To-do list</h2>
        </div>
      </div>
      <form className="task-form" onSubmit={(event) => void save(event)}>
        <label>
          <span className="sr-only">Task title</span>
          <input
            aria-label="Task title"
            disabled={pending}
            maxLength={200}
            onChange={(event) =>
              setDraft((current) => ({ ...current, title: event.target.value }))
            }
            placeholder="Add a task"
            required
            value={draft.title}
          />
        </label>
        <label>
          <span className="sr-only">Due date</span>
          <input
            aria-label="Due date"
            disabled={pending}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                due_date: event.target.value || null,
              }))
            }
            type="date"
            value={draft.due_date ?? ""}
          />
        </label>
        <button
          className="button button-primary"
          disabled={pending}
          type="submit"
        >
          {pending ? "Saving…" : editing ? "Save task" : "Add task"}
        </button>
        {editing && (
          <button
            className="button button-secondary"
            disabled={pending}
            onClick={() => {
              setEditing(null);
              setDraft(emptyTask);
            }}
            type="button"
          >
            Cancel
          </button>
        )}
      </form>
      {error && <p role="alert">{error}</p>}
      {tasks === null ? (
        <p role="status">Loading tasks…</p>
      ) : tasks.length === 0 ? (
        <p className="empty-inline">Add a task to plan your study time.</p>
      ) : (
        <ul className="task-list">
          {tasks.map((task) => (
            <li className={task.completed ? "is-complete" : ""} key={task.id}>
              <label>
                <input
                  checked={task.completed}
                  disabled={pending}
                  onChange={() => void toggle(task)}
                  type="checkbox"
                />
                <span>
                  {task.title}
                  {task.due_date && <small>Due {task.due_date}</small>}
                </span>
              </label>
              <div>
                <button
                  className="button-quiet"
                  disabled={pending}
                  onClick={() => beginEdit(task)}
                  type="button"
                >
                  Edit
                </button>
                <button
                  className="button-quiet"
                  disabled={pending}
                  onClick={() => void remove(task)}
                  type="button"
                >
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

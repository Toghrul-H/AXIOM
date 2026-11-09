"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { Application, ApplicationStatus, QuestionnaireQuestion, recruitmentApi, StaffVacancy, VacancyWrite } from "@/lib/recruitment";

const initial: VacancyWrite = { course_name: "Discrete Mathematics I", semester: "", available_positions: 1, description: "", responsibilities: "", opens_at: null, closes_at: null, state: "DRAFT" };
const local = (value: string | null) => value ? new Date(value).toISOString().slice(0, 16) : "";
const statuses: ApplicationStatus[] = ["SUBMITTED", "UNDER_REVIEW", "ACCEPTED", "REJECTED", "WITHDRAWN"];

export function DemonstratorRecruitmentManagement() {
  const [items, setItems] = useState<StaffVacancy[]>([]);
  const [form, setForm] = useState<VacancyWrite>(initial);
  const [editing, setEditing] = useState<number | null>(null);
  const [applications, setApplications] = useState<Application[]>([]);
  const [vacancyId, setVacancyId] = useState<number | null>(null);
  const [closeCandidate, setCloseCandidate] = useState<StaffVacancy | null>(null);
  const [decision, setDecision] = useState<{ application: Application; status: "ACCEPTED" | "REJECTED" } | null>(null);
  const [questionnaireVacancy, setQuestionnaireVacancy] = useState<StaffVacancy | null>(null);
  const [draftQuestions, setDraftQuestions] = useState<QuestionnaireQuestion[]>([]);
  const [message, setMessage] = useState("");
  const load = () => recruitmentApi.staff().then(setItems).catch(() => setMessage("Recruitment data could not be loaded."));

  useEffect(() => { void load(); }, []);

  async function save(event: FormEvent) {
    event.preventDefault();
    try {
      if (editing) await recruitmentApi.update(editing, form); else await recruitmentApi.create(form);
      setForm(initial); setEditing(null); setMessage("Vacancy saved."); await load();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Vacancy could not be saved."); }
  }
  function edit(vacancy: StaffVacancy) {
    setEditing(vacancy.id);
    setForm({ course_name: vacancy.course_name, semester: vacancy.semester, available_positions: vacancy.available_positions, description: vacancy.description, responsibilities: vacancy.responsibilities, opens_at: vacancy.opens_at, closes_at: vacancy.closes_at, state: vacancy.state });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  async function close() {
    if (!closeCandidate) return;
    try {
      const vacancy = closeCandidate;
      await recruitmentApi.update(vacancy.id, { course_name: vacancy.course_name, semester: vacancy.semester, available_positions: 0, description: vacancy.description, responsibilities: vacancy.responsibilities, opens_at: vacancy.opens_at, closes_at: vacancy.closes_at, state: "CLOSED" });
      setCloseCandidate(null); setMessage("Vacancy closed."); await load();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Vacancy could not be closed."); }
  }
  async function review(id: number) { try { setVacancyId(id); setApplications(await recruitmentApi.applications(id)); } catch { setMessage("Applications could not be loaded."); } }
  async function setStatus(application: Application, status: "UNDER_REVIEW" | "ACCEPTED" | "REJECTED") {
    if (!vacancyId) return;
    try {
      await recruitmentApi.setStatus(vacancyId, application.id, status);
      setDecision(null); setMessage("Application status updated."); await review(vacancyId); await load();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Application status could not be updated."); }
  }
  async function exportFile(id: number) { try { const blob = await recruitmentApi.export(id); const url = URL.createObjectURL(blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = `demonstrator-applicants-${id}.xlsx`; anchor.click(); URL.revokeObjectURL(url); } catch { setMessage("Export failed."); } }
  function editQuestionnaire(vacancy: StaffVacancy) { setQuestionnaireVacancy(vacancy); setDraftQuestions(vacancy.questionnaire.map(({ id, title, question_type, required, options }) => ({ id, title, question_type, required, options }))); }
  async function saveQuestionnaire() { if (!questionnaireVacancy) return; try { await recruitmentApi.questionnaire(questionnaireVacancy.id, draftQuestions); setMessage("Questionnaire saved."); setQuestionnaireVacancy(null); await load(); } catch (error) { setMessage(error instanceof Error ? error.message : "Questionnaire could not be saved."); } }
  function changeQuestion(index: number, patch: Partial<QuestionnaireQuestion>) { setDraftQuestions(draftQuestions.map((question, i) => i === index ? { ...question, ...patch } : question)); }
  function moveQuestion(index: number, direction: -1 | 1) { const next = [...draftQuestions], target = index + direction; if (target < 0 || target >= next.length) return; [next[index], next[target]] = [next[target], next[index]]; setDraftQuestions(next); }

  return <>
    <section><p className="eyebrow">STAFF</p><h1>Demonstrator Recruitment Management</h1></section>
    {message && <p role="alert">{message}</p>}
    {closeCandidate && <section className="panel" role="alertdialog" aria-label="Confirm vacancy closure"><h2>Close vacancy?</h2><p>Existing applications remain available, but no new application can be submitted.</p><div className="quiz-actions"><button className="button button-primary" onClick={() => void close()}>Confirm close vacancy</button><button className="button button-secondary" onClick={() => setCloseCandidate(null)}>Cancel</button></div></section>}
    {decision && <section className="panel" role="alertdialog" aria-label="Confirm application decision"><h2>{decision.status === "ACCEPTED" ? "Accept application?" : "Reject application?"}</h2><p>This decision updates the student privately and cannot be changed through this workflow.</p><div className="quiz-actions"><button className="button button-primary" onClick={() => void setStatus(decision.application, decision.status)}>Confirm {decision.status.toLowerCase()}</button><button className="button button-secondary" onClick={() => setDecision(null)}>Cancel</button></div></section>}
    {questionnaireVacancy && <section className="panel" aria-label="Questionnaire builder"><h2>Application questionnaire</h2><p>Fixed questions are required for every application and cannot be edited: full name, Neptun code, lecture grade, practice grade, practice teacher, motivation, weekly availability, preferred responsibilities, relevant experience, and additional comments.</p>{questionnaireVacancy.questionnaire_locked ? <p role="alert">This questionnaire is locked because applications already exist. Existing answers remain preserved.</p> : <><h3>Custom questions</h3>{draftQuestions.map((question, index) => <fieldset key={question.id ?? `draft-${index}`}><legend>Question {index + 1}</legend><label>Title<input value={question.title} onChange={(event) => changeQuestion(index, { title: event.target.value })} /></label><label>Type<select value={question.question_type} onChange={(event) => changeQuestion(index, { question_type: event.target.value as QuestionnaireQuestion["question_type"], options: ["SINGLE_CHOICE", "MULTIPLE_CHOICE"].includes(event.target.value) ? question.options ?? ["", ""] : null })}><option value="SHORT_TEXT">Short Text</option><option value="LONG_TEXT">Long Text</option><option value="SINGLE_CHOICE">Single Choice</option><option value="MULTIPLE_CHOICE">Multiple Choice</option><option value="YES_NO">Yes / No</option></select></label><label><input type="checkbox" checked={question.required} onChange={(event) => changeQuestion(index, { required: event.target.checked })} /> Required</label>{["SINGLE_CHOICE", "MULTIPLE_CHOICE"].includes(question.question_type) && <label>Options (one per line)<textarea value={(question.options ?? []).join("\n")} onChange={(event) => changeQuestion(index, { options: event.target.value.split("\n").filter(Boolean) })} /></label>}<div className="quiz-actions"><button type="button" onClick={() => moveQuestion(index, -1)}>Move up</button><button type="button" onClick={() => moveQuestion(index, 1)}>Move down</button><button type="button" onClick={() => setDraftQuestions(draftQuestions.filter((_, i) => i !== index))}>Remove</button></div></fieldset>)}<div className="quiz-actions"><button type="button" onClick={() => setDraftQuestions([...draftQuestions, { title: "", question_type: "SHORT_TEXT", required: false, options: null }])}>Add custom question</button><button type="button" className="button button-primary" onClick={() => void saveQuestionnaire()}>Save questionnaire</button></div><section aria-label="Student questionnaire preview"><h3>Student preview</h3><p>Fixed questions appear first, followed by:</p>{draftQuestions.length ? <ol>{draftQuestions.map((question, index) => <li key={`${question.id ?? "draft"}-${index}`}><strong>{question.title || "Untitled question"}</strong>{question.required ? " (required)" : ""}{question.options?.length ? ` — ${question.options.join(", ")}` : ""}</li>)}</ol> : <p>No custom questions yet.</p>}</section></>}<button type="button" className="button button-secondary" onClick={() => setQuestionnaireVacancy(null)}>Close</button></section>}
    <form className="panel" onSubmit={save}><h2>{editing ? "Edit vacancy" : "Create vacancy"}</h2><label>Course<input required value={form.course_name} onChange={(event) => setForm({ ...form, course_name: event.target.value })} /></label><label>Semester<input required value={form.semester} onChange={(event) => setForm({ ...form, semester: event.target.value })} /></label><label>Available positions<input required min="0" type="number" value={form.available_positions} onChange={(event) => setForm({ ...form, available_positions: Number(event.target.value) })} /></label><label>Short description<textarea required value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label><label>Responsibilities<textarea required value={form.responsibilities} onChange={(event) => setForm({ ...form, responsibilities: event.target.value })} /></label><label>Applications open<input type="datetime-local" value={local(form.opens_at)} onChange={(event) => setForm({ ...form, opens_at: event.target.value ? new Date(event.target.value).toISOString() : null })} /></label><label>Applications close<input type="datetime-local" value={local(form.closes_at)} onChange={(event) => setForm({ ...form, closes_at: event.target.value ? new Date(event.target.value).toISOString() : null })} /></label><label>State<select value={form.state} onChange={(event) => setForm({ ...form, state: event.target.value as VacancyWrite["state"] })}><option>DRAFT</option><option>OPEN</option><option>CLOSED</option></select></label><div className="quiz-actions"><button className="button button-primary">{editing ? "Save changes" : "Save vacancy"}</button>{editing && <button type="button" className="button button-secondary" onClick={() => { setEditing(null); setForm(initial); }}>Cancel edit</button>}</div></form>
    <div className="quiz-list">{items.map((vacancy) => <article className="panel" key={vacancy.id}><h2>{vacancy.course_name} · {vacancy.semester}</h2><p>{vacancy.state} · {vacancy.available_positions} position(s) · {Object.values(vacancy.status_counts).reduce((total, count) => total + count, 0)} total application(s)</p><p>{statuses.map((status) => `${status.replace("_", " ")}: ${vacancy.status_counts[status]}`).join(" · ")}</p><p>{vacancy.remaining_positions} position(s) remaining</p><div className="quiz-actions"><button className="button button-secondary" onClick={() => edit(vacancy)}>Edit Vacancy</button><button className="button button-secondary" onClick={() => editQuestionnaire(vacancy)}>Questionnaire{vacancy.questionnaire_locked ? " (locked)" : ""}</button>{vacancy.state === "OPEN" && <button className="button button-secondary" onClick={() => setCloseCandidate(vacancy)}>Close Vacancy</button>}<button className="button button-secondary" onClick={() => void review(vacancy.id)}>Review applications</button><button className="button button-secondary" onClick={() => void exportFile(vacancy.id)}>Export to Excel</button></div></article>)}</div>
    {applications.length > 0 && vacancyId && <section className="panel"><h2>Applications</h2><table><thead><tr><th>Name</th><th>Neptun Code</th><th>Lecture Grade</th><th>Application Date</th><th>Status</th><th>Questionnaire</th><th>Actions</th></tr></thead><tbody>{applications.map((application) => <tr key={application.id}><td>{application.full_name}</td><td>{application.neptun_code}</td><td>{application.lecture_grade ?? "Not provided"}</td><td>{new Date(application.submitted_at).toLocaleString()}</td><td>{application.status.replace("_", " ")}</td><td><Link href={`/teacher/recruitment/${vacancyId}/applications/${application.id}`}>View Answers</Link></td><td>{application.status === "SUBMITTED" && <button onClick={() => void setStatus(application, "UNDER_REVIEW")}>Mark Under Review</button>}{["SUBMITTED", "UNDER_REVIEW"].includes(application.status) && <><button onClick={() => setDecision({ application, status: "ACCEPTED" })}>Accept Application</button><button onClick={() => setDecision({ application, status: "REJECTED" })}>Reject Application</button></>}</td></tr>)}</tbody></table></section>}
  </>;
}

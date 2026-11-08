"use client";

import { FormEvent, useEffect, useState } from "react";
import { Application, ApplicationWrite, ApplicationStatus, recruitmentApi, Vacancy } from "@/lib/recruitment";

const blank: ApplicationWrite = { full_name: "", neptun_code: "", final_grade: null, practice_teacher: "", completion_semester: "", motivation: "", teaching_experience: "", responsibility_interest: "", additional_information: null };
const statusText: Record<ApplicationStatus, string> = {
  SUBMITTED: "Submitted — your application has been received.",
  UNDER_REVIEW: "Under Review — a lecturer is reviewing your application.",
  ACCEPTED: "Accepted — you have been selected as a demonstrator.",
  REJECTED: "Rejected — this application was not selected.",
  WITHDRAWN: "Withdrawn — your questionnaire remains available to authorized staff.",
};

export function DemonstratorOpportunities() {
  const [vacancies, setVacancies] = useState<Vacancy[]>([]);
  const [mine, setMine] = useState<Application[]>([]);
  const [form, setForm] = useState<ApplicationWrite>(blank);
  const [selected, setSelected] = useState<Vacancy | null>(null);
  const [withdrawCandidate, setWithdrawCandidate] = useState<Application | null>(null);
  const [message, setMessage] = useState("");
  const load = () => Promise.all([recruitmentApi.vacancies(), recruitmentApi.mine()]).then(([available, applications]) => { setVacancies(available); setMine(applications); });

  useEffect(() => { void load().catch(() => setMessage("Opportunities could not be loaded.")); }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    try {
      await recruitmentApi.apply(selected.id, form);
      setMessage("Application submitted.");
      setSelected(null);
      setForm(blank);
      await load();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Application could not be submitted."); }
  }

  async function withdraw() {
    if (!withdrawCandidate) return;
    try {
      await recruitmentApi.withdraw(withdrawCandidate.id);
      setWithdrawCandidate(null);
      setMessage("Application withdrawn.");
      await load();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Application could not be withdrawn."); }
  }

  return <>
    <section><p className="eyebrow">OPPORTUNITIES</p><h1>Demonstrator Opportunities</h1><p>Published opportunities for Discrete Mathematics I. Applicant counts never reveal applicant identities.</p></section>
    {message && <p role="alert" className="error-message">{message}</p>}
    {mine.length > 0 && <section className="panel"><h2>My submitted applications</h2>{mine.map((application) => <article key={application.id}><strong>{application.neptun_code} · {application.status.replace("_", " ")}</strong><p>{statusText[application.status]}</p><p>Submitted {new Date(application.submitted_at).toLocaleString()}</p>{["SUBMITTED", "UNDER_REVIEW"].includes(application.status) && <button className="button button-secondary" onClick={() => setWithdrawCandidate(application)}>Withdraw application</button>}</article>)}</section>}
    {withdrawCandidate && <section className="panel" role="alertdialog" aria-label="Confirm application withdrawal"><h2>Withdraw application?</h2><p>You cannot reapply for this vacancy. Authorized staff will retain the questionnaire for review.</p><div className="quiz-actions"><button className="button button-primary" onClick={() => void withdraw()}>Confirm withdrawal</button><button className="button button-secondary" onClick={() => setWithdrawCandidate(null)}>Cancel</button></div></section>}
    {vacancies.length === 0 ? <section className="panel"><p>No demonstrator vacancies are currently open.</p></section> : <div className="quiz-list">{vacancies.map((vacancy) => <article className="panel quiz-panel" key={vacancy.id}><h2>{vacancy.course_name} — Demonstrator Recruitment</h2><p>Semester: {vacancy.semester}</p><p>{vacancy.available_positions} position(s) available — {vacancy.applicant_count} student(s) applied</p><p>Deadline: {vacancy.closes_at ? new Date(vacancy.closes_at).toLocaleString() : "To be announced"}</p><p>{vacancy.description}</p><h3>Responsibilities</h3><p>{vacancy.responsibilities}</p><p><strong>{vacancy.application_open ? "Applications are open." : "Applications are not currently open."}</strong></p>{vacancy.application_open && <button className="button button-primary" onClick={() => { setSelected(vacancy); setMessage(""); }}>Apply Now</button>}</article>)}</div>}
    {selected && <form className="panel" onSubmit={submit}><h2>Apply: {selected.course_name}</h2><p>Review your answers before submitting; submitted applications cannot be edited.</p>{([['full_name', 'Full name'], ['neptun_code', 'Neptun code'], ['final_grade', 'Final grade (optional)'], ['practice_teacher', "Practice teacher's name"], ['completion_semester', 'Semester completed'], ['motivation', 'Why do you want to become a demonstrator?'], ['teaching_experience', 'Teaching or tutoring experience'], ['responsibility_interest', 'Responsibilities that interest you most'], ['additional_information', 'Additional information (optional)']] as const).map(([key, label]) => <label key={key}>{label}<textarea required={!['final_grade', 'additional_information'].includes(key)} value={(form[key] ?? "") as string} onChange={(event) => setForm({ ...form, [key]: event.target.value || null })} /></label>)}<div className="quiz-actions"><button className="button button-primary">Submit application</button><button type="button" className="button button-secondary" onClick={() => setSelected(null)}>Cancel</button></div></form>}
  </>;
}

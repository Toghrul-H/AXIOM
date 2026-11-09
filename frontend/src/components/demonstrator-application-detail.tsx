"use client";

import { useEffect, useState } from "react";
import { Application, recruitmentApi } from "@/lib/recruitment";

const shown = (value: string | number | string[] | boolean | null) => Array.isArray(value) ? value.join(", ") : typeof value === "boolean" ? (value ? "Yes" : "No") : value ?? "Not provided";
export function DemonstratorApplicationDetail({ vacancyId, applicationId }: { vacancyId: number; applicationId: number }) {
  const [item, setItem] = useState<Application | null>(null); const [error, setError] = useState("");
  useEffect(() => { void recruitmentApi.application(vacancyId, applicationId).then(setItem).catch((event: Error) => setError(event.message || "Application could not be loaded.")); }, [vacancyId, applicationId]);
  if (error) return <p role="alert">{error}</p>; if (!item) return <p role="status">Loading application…</p>;
  return <section className="panel"><p className="eyebrow">STAFF-ONLY QUESTIONNAIRE</p><h1>{item.full_name}</h1><p><strong>Neptun code:</strong> {item.neptun_code}</p><p><strong>Lecture grade:</strong> {shown(item.lecture_grade)}</p><p><strong>Practice grade:</strong> {shown(item.practice_grade)}</p>{item.legacy_final_grade && <p><strong>Legacy final grade:</strong> {item.legacy_final_grade}</p>}{item.legacy_completion_semester && <p><strong>Legacy completion semester:</strong> {item.legacy_completion_semester}</p>}<p><strong>Practice teacher:</strong> {shown(item.practice_teacher)}</p><p><strong>Weekly availability:</strong> {item.weekly_availability === null ? "Not provided" : `${item.weekly_availability} hour(s)`}</p><p><strong>Preferred responsibilities:</strong> {shown(item.preferred_responsibilities)}</p><p><strong>Submitted:</strong> {new Date(item.submitted_at).toLocaleString()}</p><h2>Motivation</h2><p>{shown(item.motivation)}</p><h2>Relevant experience</h2><p>{shown(item.relevant_experience)}</p><h2>Additional comments</h2><p>{shown(item.additional_comments)}</p>{item.custom_answers.length > 0 && <><h2>Custom questions</h2>{item.custom_answers.map((answer) => <article key={answer.question_id}><h3>{answer.question_title}</h3><p>{shown(answer.answer)}</p></article>)}</>}</section>;
}

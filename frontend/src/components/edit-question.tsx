"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Question, questionsApi } from "@/lib/questions";
import { QuestionForm } from "./question-form";

export function EditQuestion({ id }: { id: string }) {
  const [question, setQuestion] = useState<Question | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    questionsApi
      .get(id, controller.signal)
      .then(setQuestion)
      .catch((e: Error) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => controller.abort();
  }, [id]);
  if (error)
    return (
      <div className="panel error-state" role="alert">
        <h1>Question unavailable</h1>
        <p>{error}</p>
        <Link href="/teacher/questions" className="button button-secondary">
          Back to Question Bank
        </Link>
      </div>
    );
  if (!question)
    return (
      <div className="panel loading-state" role="status">
        Loading question…
      </div>
    );
  return <QuestionForm question={question} />;
}

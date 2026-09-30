"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { quizzesApi, Review, ReviewItem } from "@/lib/quizzes";
import { PageHeading } from "./page-heading";
export function QuizResults({
  id,
  allAnswers = false,
}: {
  id: string;
  allAnswers?: boolean;
}) {
  const [data, setData] = useState<Review | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    quizzesApi
      .review(id)
      .then((r) => {
        if (live) setData(r);
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [id]);
  if (error)
    return (
      <p role="alert" className="error-message">
        {error}{" "}
        <Link href={`/student/quizzes/attempts/${id}`}>Return to attempt</Link>
      </p>
    );
  if (!data) return <p role="status">Loading submitted results…</p>;
  return (
    <>
      <PageHeading
        eyebrow={allAnswers ? "REVIEW ALL ANSWERS" : "QUIZ RESULTS"}
        title={data.quiz_title}
        description={`Submitted ${new Date(data.submitted_at!).toLocaleString()}`}
      />
      <div className="panel quiz-panel">
        <h2>
          {data.objective_total
            ? `Automatically graded points: ${data.objective_score} / ${data.objective_total}`
            : "No automatically gradable questions"}
        </h2>
        <p>
          {data.correct_count} correct · {data.incorrect_count} incorrect
          (including {data.unanswered_objective_count} unanswered objective
          questions)
        </p>
        <p>
          {data.ungraded_count} written response
          {data.ungraded_count === 1 ? " is" : "s are"} not automatically
          graded.
        </p>
        <div className="quiz-actions">
          {!allAnswers && (
            <Link
              className="button button-primary"
              href={`/student/quizzes/attempts/${id}/review`}
            >
              Review All Answers
            </Link>
          )}
          <Link className="button button-secondary" href="/student/quizzes">
            Quizzes and previous attempts
          </Link>
        </div>
      </div>
      <p className="quiz-notice">
        Scores, answer checks, solutions, and feedback provided on this platform
        are intended for learning and practice purposes only. They do not
        constitute official assessment or guarantee the same score in a
        university examination. Official assessment may consider reasoning,
        justification, notation, method, completeness, and other marking
        criteria.
      </p>
      {allAnswers && (
        <div className="quiz-list">
          {data.items.map((item, i) => (
            <article className="panel quiz-panel quiz-review" key={item.id}>
              <p>
                Question {i + 1} ·{" "}
                {!item.auto_gradable
                  ? "Not automatically graded"
                  : !item.answered
                    ? "Not answered"
                    : item.is_correct
                      ? "Correct"
                      : "Incorrect"}
              </p>
              <h2>{item.question_text}</h2>
              <h3>Your answer</h3>
              <p>{submittedText(item)}</p>
              <h3>
                {item.auto_gradable ? "Correct answer" : "Reference answer"}
              </h3>
              <p>{correctText(item)}</p>
              <h3>Explanation / full solution</h3>
              <p>
                {item.explanation ??
                  "No explanation has been supplied for this question."}
              </p>
              {item.auto_gradable && (
                <p>
                  {item.points_awarded} / {item.points} points
                </p>
              )}
            </article>
          ))}
        </div>
      )}
    </>
  );
}
function submittedText(i: ReviewItem) {
  if (!i.answered) return "Not answered";
  if (i.response_type === "FREE_RESPONSE") return i.free_response;
  if (i.response_type === "TRUE_FALSE")
    return i.boolean_answer ? "True" : "False";
  return i.options
    .filter((o) => i.selected_option_ids.includes(o.id))
    .map((o) => o.text)
    .join("; ");
}
function correctText(i: ReviewItem) {
  if (i.response_type === "FREE_RESPONSE")
    return i.expected_answer ?? "No reference answer supplied.";
  if (i.response_type === "TRUE_FALSE")
    return i.correct_boolean ? "True" : "False";
  return i.options
    .filter((o) => i.correct_option_ids.includes(o.id))
    .map((o) => o.text)
    .join("; ");
}

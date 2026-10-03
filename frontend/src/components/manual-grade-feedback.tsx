import type { ReviewItem } from "@/lib/quizzes";

export function ManualGradeFeedback({ item }: { item: ReviewItem }) {
  if (item.response_type !== "FREE_RESPONSE") return null;
  const completed =
    item.manual_grading_status === "COMPLETED" && item.manual_points != null;
  return (
    <section className="quiz-notice" aria-label="Manual grading">
      <h3>Manual grading</h3>
      {completed ? (
        <>
          <p>
            <strong>
              Graded · {item.manual_points} / {item.points} points
            </strong>
          </p>
          {item.manual_feedback && (
            <>
              <h3>Staff feedback</h3>
              <p className="quiz-question">{item.manual_feedback}</p>
            </>
          )}
          {item.graded_at && (
            <p>Graded {new Date(item.graded_at).toLocaleString()}</p>
          )}
        </>
      ) : (
        <>
          <p>
            <strong>Pending manual review</strong>
          </p>
          <p>This written response has not yet been graded by course staff.</p>
        </>
      )}
    </section>
  );
}

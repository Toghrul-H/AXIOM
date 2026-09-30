export type Performance = {
  answered_count: number;
  auto_graded_count: number;
  correct_count: number;
  accuracy_percent: number | null;
};
export type ProgressData = {
  overview: {
    completed_quizzes: number;
    completed_attempts: number;
    questions_answered: number;
    auto_graded_questions: number;
    auto_graded_correct: number;
    auto_graded_accuracy: number | null;
  };
  topics: (Performance & { slug: string; name: string })[];
  skills: (Performance & { code: string; name: string })[];
  unattributed_topic: Performance;
  unattributed_skill: Performance;
  recent_attempts: (Performance & {
    id: string;
    quiz_id: number;
    quiz_title: string;
    submitted_at: string;
    total_question_count: number;
    objective_score: number;
    objective_total: number;
  })[];
};

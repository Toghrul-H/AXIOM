export type DemoRole = "student" | "lecturer";
export type DemoSection =
  | "dashboard"
  | "course"
  | "quiz"
  | "tasks"
  | "notifications"
  | "materials"
  | "messages";
export type DemoQuestionType =
  "multiple_choice" | "true_false" | "free_response";
export type DemoDifficulty = "easy" | "medium" | "hard";
export type DemoQuestion = {
  id: string;
  title: string;
  text: string;
  type: DemoQuestionType;
  difficulty: DemoDifficulty;
};
export type DemoAssessment = {
  id: string;
  title: string;
  description: string;
  questionIds: string[];
  published: boolean;
  durationMinutes: number;
};
export type DemoLesson = {
  id: string;
  title: string;
  content: string;
  published: boolean;
};
export type DemoSubmission = {
  id: string;
  studentLabel: string;
  question: string;
  response: string;
  criteria: string;
  status: "ungraded" | "graded";
  score?: number;
  feedback?: string;
};
export type DemoQuizQuestion = {
  id: string;
  prompt: string;
  options: string[];
  correctIndex: number;
  explanation: string;
};
export type DemoTask = { id: string; title: string; completed: boolean };
export type DemoNotification = {
  id: string;
  title: string;
  read: boolean;
  target: DemoSection;
};
export type DemoMessage = {
  id: string;
  author: string;
  text: string;
  mine: boolean;
};

export type DemoState = {
  activeSection: DemoSection;
  completedLessonIds: string[];
  tasks: DemoTask[];
  notifications: DemoNotification[];
  submissions: DemoSubmission[];
  messages: DemoMessage[];
  questions: DemoQuestion[];
  assessments: DemoAssessment[];
  lessons: DemoLesson[];
  quizIndex: number;
  quizAnswers: Record<string, number>;
  quizSubmitted: boolean;
};

export const demoFixtures = {
  course: {
    title: "Foundations of Discrete Mathematics",
    chapters: [
      {
        id: "logic",
        title: "Propositional logic",
        lessons: [
          {
            id: "truth",
            title: "Truth tables",
            content:
              "A proposition is a statement with a truth value. A truth table lists every assignment of truth values to its variables.",
          },
          {
            id: "implication",
            title: "Implication and equivalence",
            content:
              "The implication p → q is false only when p is true and q is false. Equivalence is true when both propositions have the same truth value.",
          },
        ],
      },
      {
        id: "sets",
        title: "Sets and relations",
        lessons: [
          {
            id: "sets-intro",
            title: "Set operations",
            content:
              "Union collects elements from either set; intersection keeps elements shared by both sets.",
          },
        ],
      },
      {
        id: "counting",
        title: "Counting principles",
        lessons: [
          {
            id: "counting-intro",
            title: "The multiplication principle",
            content:
              "If a first choice has m outcomes and an independent second choice has n outcomes, there are m × n combined outcomes.",
          },
        ],
      },
    ],
  },
  quiz: {
    title: "Logic and sets check-in",
    questions: [
      {
        id: "q1",
        prompt: "When is p → q false?",
        options: [
          "p is false and q is true",
          "p is true and q is false",
          "p and q are both true",
          "p and q are both false",
        ],
        correctIndex: 1,
        explanation: "An implication has one false case: true → false.",
      },
      {
        id: "q2",
        prompt: "If A = {1, 2} and B = {2, 3}, what is A ∩ B?",
        options: ["{1, 2, 3}", "{1, 3}", "{2}", "∅"],
        correctIndex: 2,
        explanation: "Intersection contains elements present in both sets.",
      },
      {
        id: "q3",
        prompt: "How many subsets does a set with three elements have?",
        options: ["3", "6", "8", "9"],
        correctIndex: 2,
        explanation: "A set with n elements has 2ⁿ subsets, so 2³ = 8.",
      },
      {
        id: "q4",
        prompt: "Which is equivalent to ¬(p ∧ q)?",
        options: ["¬p ∧ ¬q", "¬p ∨ ¬q", "p ∨ q", "p ∧ ¬q"],
        correctIndex: 1,
        explanation:
          "De Morgan's law distributes negation over conjunction as a disjunction.",
      },
      {
        id: "q5",
        prompt: "A relation R on a set A is reflexive when:",
        options: [
          "aRb for every a and b",
          "aRa for every a in A",
          "aRb implies bRa",
          "aRb and bRc imply aRc",
        ],
        correctIndex: 1,
        explanation: "Reflexivity requires every element to relate to itself.",
      },
      {
        id: "q6",
        prompt: "The sum of degrees in an undirected graph equals:",
        options: [
          "the number of vertices",
          "the number of edges",
          "twice the number of edges",
          "twice the number of vertices",
        ],
        correctIndex: 2,
        explanation:
          "Each edge contributes one degree to each of its two endpoints.",
      },
      {
        id: "q7",
        prompt: "What is C(5, 2)?",
        options: ["5", "10", "20", "25"],
        correctIndex: 1,
        explanation: "C(5, 2) = 5 × 4 / 2 = 10.",
      },
      {
        id: "q8",
        prompt:
          "If 11 objects are placed into 10 boxes, the pigeonhole principle guarantees:",
        options: [
          "every box is occupied",
          "one box has at least two objects",
          "two boxes are empty",
          "all boxes have one object",
        ],
        correctIndex: 1,
        explanation: "More objects than boxes guarantees a repeated box.",
      },
    ] satisfies DemoQuizQuestion[],
  },
  materials: ["Sample logic notation guide", "Sample sets worksheet"],
  initialState: {
    activeSection: "dashboard",
    completedLessonIds: [],
    tasks: [
      {
        id: "task-logic",
        title: "Review truth-table notation",
        completed: false,
      },
      {
        id: "task-sets",
        title: "Complete the sample sets worksheet",
        completed: false,
      },
    ],
    notifications: [
      {
        id: "notice-lesson",
        title: "New lesson: implication and equivalence",
        read: false,
        target: "course",
      },
      {
        id: "notice-quiz",
        title: "Logic and sets check-in is available",
        read: false,
        target: "quiz",
      },
    ],
    submissions: [
      {
        id: "submission-1",
        studentLabel: "Sample Student A",
        question: "Show that A ∩ B is a subset of A.",
        response: "Every element in the intersection belongs to A.",
        criteria: "Identify membership reasoning and use precise set notation.",
        status: "ungraded",
      },
      {
        id: "submission-2",
        studentLabel: "Sample Student B",
        question: "State the contrapositive of p → q.",
        response: "¬q → ¬p.",
        criteria: "State the logically equivalent implication correctly.",
        status: "ungraded",
      },
    ],
    messages: [
      {
        id: "message-1",
        author: "Sample Study Partner",
        text: "Would you like to compare truth tables?",
        mine: false,
      },
    ],
    questions: [
      {
        id: "bank-1",
        title: "Implication",
        text: "When is p → q false?",
        type: "multiple_choice",
        difficulty: "easy",
      },
      {
        id: "bank-2",
        title: "Set intersection",
        text: "Find A ∩ B for two finite sample sets.",
        type: "multiple_choice",
        difficulty: "easy",
      },
      {
        id: "bank-3",
        title: "Pigeonhole principle",
        text: "Explain why two objects share a box when objects outnumber boxes.",
        type: "free_response",
        difficulty: "medium",
      },
    ],
    assessments: [
      {
        id: "assessment-1",
        title: "Midterm practice",
        description: "An original demonstration assessment.",
        questionIds: ["bank-1", "bank-2"],
        published: true,
        durationMinutes: 30,
      },
    ],
    lessons: [
      {
        id: "lesson-pigeonhole",
        title: "The pigeonhole principle",
        content:
          "If more objects are placed into fewer boxes, at least one box contains at least two objects.",
        published: false,
      },
    ],
    quizIndex: 0,
    quizAnswers: {},
    quizSubmitted: false,
  } satisfies DemoState,
};

export function freshDemoState(): DemoState {
  return JSON.parse(JSON.stringify(demoFixtures.initialState)) as DemoState;
}

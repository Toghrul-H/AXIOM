import { apiFetch, authRequest } from "./auth";

export type ApplicationStatus = "SUBMITTED" | "UNDER_REVIEW" | "ACCEPTED" | "REJECTED" | "WITHDRAWN";
export type QuestionType = "SHORT_TEXT" | "LONG_TEXT" | "SINGLE_CHOICE" | "MULTIPLE_CHOICE" | "YES_NO";
export type QuestionnaireQuestion = { id?: number; title: string; question_type: QuestionType; required: boolean; options: string[] | null; display_order?: number };
export type Vacancy = { id: number; course_name: string; semester: string; available_positions: number; description: string; responsibilities: string; opens_at: string | null; closes_at: string | null; state: "DRAFT" | "OPEN" | "CLOSED"; applicant_count: number; application_open: boolean; questionnaire: QuestionnaireQuestion[] };
export type StaffVacancy = Vacancy & { status_counts: Record<ApplicationStatus, number>; accepted_count: number; remaining_positions: number; questionnaire_locked: boolean };
export type CustomAnswer = { question_id: number; question_title: string; question_type: QuestionType; answer: string | string[] | boolean | null; display_order: number };
export type Application = { id: number; vacancy_id: number; full_name: string; neptun_code: string; lecture_grade: string | null; practice_grade: string | null; legacy_final_grade: string | null; legacy_completion_semester: string | null; practice_teacher: string | null; motivation: string | null; weekly_availability: number | null; preferred_responsibilities: string[] | null; relevant_experience: string | null; additional_comments: string | null; custom_answers: CustomAnswer[]; status: ApplicationStatus; submitted_at: string; decision_at: string | null };
export type ApplicationWrite = { full_name: string; neptun_code: string; lecture_grade: string; practice_grade: string; practice_teacher: string; motivation: string; weekly_availability: number; preferred_responsibilities: string[]; relevant_experience: string | null; additional_comments: string | null; custom_answers: Record<number, string | string[] | boolean | null> };
export type VacancyWrite = Omit<Vacancy, "id" | "applicant_count" | "application_open" | "questionnaire">;

export const recruitmentApi = {
  vacancies: () => authRequest<Vacancy[]>("/recruitment/demonstrator-vacancies"),
  mine: () => authRequest<Application[]>("/recruitment/demonstrator-applications/me"),
  apply: (id: number, payload: ApplicationWrite) => authRequest<Application>(`/recruitment/demonstrator-vacancies/${id}/applications`, "POST", payload),
  withdraw: (id: number) => authRequest<Application>(`/recruitment/demonstrator-applications/${id}/withdraw`, "POST"),
  staff: () => authRequest<StaffVacancy[]>("/recruitment/staff/demonstrator-vacancies"),
  create: (payload: VacancyWrite) => authRequest<StaffVacancy>("/recruitment/staff/demonstrator-vacancies", "POST", payload),
  update: (id: number, payload: VacancyWrite) => authRequest<StaffVacancy>(`/recruitment/staff/demonstrator-vacancies/${id}`, "PATCH", payload),
  questionnaire: (id: number, questions: QuestionnaireQuestion[]) => authRequest<QuestionnaireQuestion[]>(`/recruitment/staff/demonstrator-vacancies/${id}/questionnaire`, "PUT", { questions }),
  applications: (id: number) => authRequest<Application[]>(`/recruitment/staff/demonstrator-vacancies/${id}/applications`),
  application: (vacancyId: number, id: number) => authRequest<Application>(`/recruitment/staff/demonstrator-vacancies/${vacancyId}/applications/${id}`),
  setStatus: (vacancyId: number, id: number, status: "UNDER_REVIEW" | "ACCEPTED" | "REJECTED") => authRequest<Application>(`/recruitment/staff/demonstrator-vacancies/${vacancyId}/applications/${id}`, "PATCH", { status }),
  export: async (id: number) => { const response = await apiFetch(`/recruitment/staff/demonstrator-vacancies/${id}/applications.xlsx`); if (!response.ok) throw new Error("Export failed"); return response.blob(); },
};

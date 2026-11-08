import { apiFetch, authRequest } from "./auth";

export type ApplicationStatus = "SUBMITTED" | "UNDER_REVIEW" | "ACCEPTED" | "REJECTED" | "WITHDRAWN";
export type Vacancy = {
  id: number; course_name: string; semester: string; available_positions: number;
  description: string; responsibilities: string; opens_at: string | null; closes_at: string | null;
  state: "DRAFT" | "OPEN" | "CLOSED"; applicant_count: number; application_open: boolean;
};
export type StaffVacancy = Vacancy & { status_counts: Record<ApplicationStatus, number>; accepted_count: number; remaining_positions: number };
export type Application = {
  id: number; vacancy_id: number; full_name: string; neptun_code: string; final_grade: string | null;
  practice_teacher: string; completion_semester: string; motivation: string; teaching_experience: string;
  responsibility_interest: string; additional_information: string | null; status: ApplicationStatus;
  submitted_at: string; decision_at: string | null;
};
export type ApplicationWrite = Omit<Application, "id" | "vacancy_id" | "status" | "submitted_at" | "decision_at">;
export type VacancyWrite = Omit<Vacancy, "id" | "applicant_count" | "application_open">;

export const recruitmentApi = {
  vacancies: () => authRequest<Vacancy[]>("/recruitment/demonstrator-vacancies"),
  mine: () => authRequest<Application[]>("/recruitment/demonstrator-applications/me"),
  apply: (id: number, payload: ApplicationWrite) => authRequest<Application>(`/recruitment/demonstrator-vacancies/${id}/applications`, "POST", payload),
  withdraw: (id: number) => authRequest<Application>(`/recruitment/demonstrator-applications/${id}/withdraw`, "POST"),
  staff: () => authRequest<StaffVacancy[]>("/recruitment/staff/demonstrator-vacancies"),
  create: (payload: VacancyWrite) => authRequest<StaffVacancy>("/recruitment/staff/demonstrator-vacancies", "POST", payload),
  update: (id: number, payload: VacancyWrite) => authRequest<StaffVacancy>(`/recruitment/staff/demonstrator-vacancies/${id}`, "PATCH", payload),
  applications: (id: number) => authRequest<Application[]>(`/recruitment/staff/demonstrator-vacancies/${id}/applications`),
  application: (vacancyId: number, id: number) => authRequest<Application>(`/recruitment/staff/demonstrator-vacancies/${vacancyId}/applications/${id}`),
  setStatus: (vacancyId: number, id: number, status: "UNDER_REVIEW" | "ACCEPTED" | "REJECTED") => authRequest<Application>(`/recruitment/staff/demonstrator-vacancies/${vacancyId}/applications/${id}`, "PATCH", { status }),
  export: async (id: number) => {
    const response = await apiFetch(`/recruitment/staff/demonstrator-vacancies/${id}/applications.xlsx`);
    if (!response.ok) throw new Error("Export failed");
    return response.blob();
  },
};

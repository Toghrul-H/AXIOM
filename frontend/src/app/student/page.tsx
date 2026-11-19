"use client";

import { StudentDashboard } from "@/components/student-dashboard";
import { StudentPreviewDashboard } from "@/components/student-preview-dashboard";
import { useAuth } from "@/components/auth-provider";
export default function Page() {
  const { studentView } = useAuth();
  return studentView ? <StudentPreviewDashboard /> : <StudentDashboard />;
}

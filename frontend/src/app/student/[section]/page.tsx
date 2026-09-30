import { notFound, redirect } from "next/navigation";
import { StudentPreview } from "@/components/student-preview";
import { StudentProgress } from "@/components/student-progress";
export default async function Page({
  params,
}: {
  params: Promise<{ section: string }>;
}) {
  const { section } = await params;
  if (section === "progress") return <StudentProgress />;
  if (section === "practice") redirect("/student/quizzes");
  if (section !== "learn") notFound();
  return <StudentPreview section={section} />;
}

import { QuizResults } from "@/components/quiz-results";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <QuizResults id={id} />;
}

import { TakeQuiz } from "@/components/take-quiz";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <TakeQuiz id={id} />;
}

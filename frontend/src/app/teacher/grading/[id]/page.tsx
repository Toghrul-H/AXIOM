import { AttemptGrading } from "@/components/manual-grading";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <AttemptGrading key={id} id={id} />;
}

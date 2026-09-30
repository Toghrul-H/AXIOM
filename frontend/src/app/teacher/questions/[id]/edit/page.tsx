import { notFound } from "next/navigation";
import { EditQuestion } from "@/components/edit-question";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  if (!/^[1-9]\d*$/.test(id)) notFound();
  return <EditQuestion key={id} id={id} />;
}

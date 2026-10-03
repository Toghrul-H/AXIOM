import { CheckEmail } from "@/components/email-verification";
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ registered?: string }>;
}) {
  return <CheckEmail registered={(await searchParams).registered === "1"} />;
}

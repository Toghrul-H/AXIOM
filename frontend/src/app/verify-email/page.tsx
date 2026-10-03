import type { Metadata } from "next";
import { VerifyEmail } from "@/components/email-verification";
export const metadata: Metadata = {
  referrer: "no-referrer",
  robots: { index: false, follow: false },
};
export default function Page() {
  return <VerifyEmail />;
}

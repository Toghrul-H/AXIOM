import type { Metadata } from "next";
import { ForgotPassword } from "@/components/password-recovery";

export const metadata: Metadata = {
  title: "Forgot password · AXIOM",
  referrer: "no-referrer",
  robots: { index: false, follow: false },
};
export const dynamic = "force-dynamic";
export const revalidate = 0;

export default function Page() {
  return <ForgotPassword />;
}

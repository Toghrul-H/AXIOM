import type { Metadata } from "next";
import { AuthProvider } from "@/components/auth-provider";
import "./globals.css";
import "./question-bank.css";
import "./quizzes.css";
import "./axiom.css";

export const metadata: Metadata = {
  title: "AXIOM · Discrete Mathematics",
  description: "ELTE Faculty of Informatics · Teaching and learning workspace",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}

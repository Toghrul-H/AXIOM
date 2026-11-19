import type { Metadata } from "next";
import Script from "next/script";
import { AuthProvider } from "@/components/auth-provider";
import "katex/dist/katex.min.css";
import "./globals.css";
import "./question-bank.css";
import "./quizzes.css";
import "./axiom.css";

export const metadata: Metadata = {
  title: "AXIOM · Discrete Mathematics",
  description: "ELTE Faculty of Informatics · Teaching and learning workspace",
};

const themeBootstrap = `(() => { try {
  const key = "axiom-appearance";
  const saved = localStorage.getItem(key);
  const preference = saved === "light" || saved === "dark" || saved === "system" ? saved : "system";
  const theme = preference === "system"
    ? (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
    : preference;
  document.documentElement.dataset.theme = theme;
  document.documentElement.dataset.themePreference = preference;
  document.documentElement.style.colorScheme = theme;
} catch (_) {} })();`;

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <Script id="axiom-theme" strategy="beforeInteractive">
          {themeBootstrap}
        </Script>
      </head>
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
